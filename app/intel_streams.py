"""Intel Streams add-on (tab "🗂 Intel Streams", deep link #intel): five informational data streams for blackout.network.
  Research  OpenAlex API, arXiv RSS (cs.CR, physics.space-ph, q-bio.PE, eess.SY), PubMed E-utilities, medRxiv/bioRxiv API
            (stand-in for Google Scholar, which has no API and forbids automated access)
  Leaks     wikileaks.org release listing (-Leaks-.html) and news page (-News-.html): flags any release newer than the last one seen
  Patents   EPO Publication Server REST (data.epo.org, keyless): weekly European patent publications, filtered to a watch list of major
            tech / defense / biotech / energy applicants
  M&A       SEC EDGAR full-text search (takeover filings: SC TO-T, SC 14D9, DEFM14A, PREM14A, S-4, F-4) + PR Newswire / Guardian M&A RSS: deals >= $1B
            or defense / critical-infrastructure deals
  Markets   Yahoo Finance chart API (index / FX / commodity / volatility moves past fixed thresholds), FDIC bank failures API,
            Fed, ECB, BoE, BoJ, BLS, BEA release feeds, BBC / Guardian / CNBC / MarketWatch / DW business RSS (bank failures,
            currency crises, market crashes)
Every item is link-checked (2xx/3xx) before it is published; nothing is generated. Items never feed scoring, ranks or The Wire.
Writes only intel_streams.db. Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py, config.json or blackout.db.
Box: `python3 intel_streams.py loop` (run_intel_streams.sh) collects on the scan interval (config.json interval_minutes, read-only).
Public node (BN_WEB_ONLY=1): read-only view of the synced intel_streams.db."""
import os, re, sys, json, time, sqlite3, hashlib, html, gzip, threading, urllib.parse, urllib.request, urllib.error
import xml.etree.ElementTree as ET
import concurrent.futures as cf
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

BASE = os.path.dirname(os.path.abspath(__file__)); DB = os.path.join(BASE, "intel_streams.db")
STATIC = os.path.join(BASE, "intel_static"); FILES = {"app.js": "application/javascript", "app.css": "text/css"}
WEB_ONLY = os.environ.get("BN_WEB_ONLY") == "1"
UA = "Mozilla/5.0 (compatible; blackout.network research monitor; hello@blackout.network)"   # SEC asks for a contact address in the UA
SEC_UA = "blackout.network research monitor hello@blackout.network"
MAILTO = "hello@blackout.network"
STREAMS = {"research": "Research", "leaks": "Leaks", "patents": "Patents", "mna": "M&A", "markets": "Markets"}
DEDUPE_H = 12
KEEP_DAYS = 30

def now(): return datetime.now(timezone.utc)
def iso(d=None): return (d or now()).strftime("%Y-%m-%dT%H:%M:%SZ")
def log(m): print(time.strftime("[%Y-%m-%d %H:%M:%S] "), m, flush=True)

# ------------------------------------------------------------------ storage
SCHEMA = """
CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY, stream TEXT, source TEXT, title TEXT, url TEXT, published TEXT, found TEXT,
  summary TEXT, tags TEXT, extra TEXT, tkey TEXT, link_status INTEGER, link_note TEXT);
CREATE INDEX IF NOT EXISTS ix_items_stream ON items(stream, found);
CREATE INDEX IF NOT EXISTS ix_items_tkey ON items(tkey, found);
CREATE TABLE IF NOT EXISTS runs(source TEXT, stream TEXT, ts TEXT, ok INTEGER, n_new INTEGER, n_seen INTEGER, error TEXT);
CREATE TABLE IF NOT EXISTS state(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS epo_seen(pn TEXT PRIMARY KEY, week TEXT, applicant TEXT, title TEXT, matched TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS rejected(url TEXT PRIMARY KEY, stream TEXT, title TEXT, code TEXT, ts TEXT);
"""
def db(ro=False):
    if ro:
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=15)
    else:
        c = sqlite3.connect(DB, timeout=30); c.executescript(SCHEMA); c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row; return c
def sget(c, k, d=None):
    r = c.execute("SELECT v FROM state WHERE k=?", (k,)).fetchone()
    return json.loads(r[0]) if r else d
def sset(c, k, v): c.execute("INSERT OR REPLACE INTO state VALUES(?,?)", (k, json.dumps(v)))

# ------------------------------------------------------------------ HTTP + link verification
def http(url, timeout=30, accept="application/json", ua=UA, headers=None, limit=25_000_000):
    h = {"User-Agent": ua, "Accept": accept, "Accept-Encoding": "gzip"}; h.update(headers or {})
    r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
    b = r.read(limit)
    return gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b
def getjson(url, **kw): return json.loads(http(url, **kw))

class _NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
_noredir = urllib.request.build_opener(_NoRedir)
def check_link(url):
    """-> (ok, code, note). ok when the link answers 2xx, or 3xx to a page that is not 404/410/5xx.
    Publishers that answer the final hop with 401/403/429 (bot walls behind a DOI/Google News redirect) count as ok, noted."""
    if not re.match(r"^https?://", url or ""): return False, 0, "not http(s)"
    ua = SEC_UA if "sec.gov" in url else UA
    hd = {"User-Agent": ua, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Range": "bytes=0-4095"}
    first = None
    for method in ("HEAD", "GET"):
        try:
            r = _noredir.open(urllib.request.Request(url, headers=hd, method=method), timeout=25); first = r.status; r.close(); break
        except urllib.error.HTTPError as e:
            first = e.code
            if 300 <= e.code < 400: break
            if method == "GET": return False, e.code, f"HTTP {e.code}"
        except Exception as ex:
            if method == "GET": return False, 0, type(ex).__name__
    if first and 200 <= first < 300: return True, first, ""
    if first and 300 <= first < 400:
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=hd), timeout=25); code = r.status; r.close()
            return True, first, f"{first} -> {code}"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 429, 405, 406, 451): return True, first, f"{first} -> {e.code} (destination blocks automated checks)"
            return False, e.code, f"{first} -> HTTP {e.code}"
        except Exception as ex: return True, first, f"{first} -> {type(ex).__name__}"
    return False, first or 0, f"HTTP {first}"

# ------------------------------------------------------------------ parsing helpers
TAG = re.compile(r"<[^>]+>")
def clean(s, n=400): return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", s or ""))).strip()[:n]
def tkey(t): return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()[:80]
def pdate(s):
    if not s: return None
    try: return iso(parsedate_to_datetime(s).astimezone(timezone.utc))
    except Exception: pass
    for f in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%d %B %Y"):
        try:
            d = datetime.strptime(s.strip()[:25], f)
            return iso(d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc))
        except Exception: pass
    return None
def rss(url, limit=60, ua=UA):
    root = ET.fromstring(http(url, accept="application/rss+xml, application/atom+xml, application/xml, text/xml", ua=ua))
    out = []; A = "{http://www.w3.org/2005/Atom}"
    for it in list(root.iter("item")) + list(root.iter("{http://purl.org/rss/1.0/}item")):
        g = lambda t: (it.findtext(t) or it.findtext("{http://purl.org/rss/1.0/}" + t) or "")
        src = it.find("source")
        out.append({"title": clean(g("title"), 300), "url": g("link").strip(), "time": pdate(g("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")),
                    "summary": clean(g("description"), 500), "source": (src.text or "").strip() if src is not None else ""})
    for it in root.iter(A + "entry"):
        l = it.find(A + "link"); out.append({"title": clean(it.findtext(A + "title"), 300), "url": (l.get("href") if l is not None else ""), "source": "",
                                             "time": pdate(it.findtext(A + "updated") or it.findtext(A + "published")), "summary": clean(it.findtext(A + "summary"), 500)})
    return out[:limit]
def gnews(q, limit=25):
    items = rss("https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}), limit)
    for x in items:
        if x["source"] and x["title"].endswith(" - " + x["source"]): x["title"] = x["title"][: -len(x["source"]) - 3]
        x["summary"] = ""
    return items

# ------------------------------------------------------------------ keyword filters
RESEARCH_TOPICS = [
    ("Cyber", r"\b(cyber ?attack|cyber ?security|ransomware|malware|botnet|phishing|zero[- ]day|vulnerabilit|exploit|intrusion detection|apt\b|ddos|supply[- ]chain attack|jailbreak|adversarial attack|backdoor|side[- ]channel|scada|industrial control)"),
    ("Disease", r"\b(outbreak|pandemic|epidemic|pathogen|avian influenza|h5n1|h5n5|influenza a|mpox|ebola|marburg|nipah|cholera|dengue|measles|antimicrobial resistance|zoonotic|emerging infectious|bioterror|biosecurity|biological weapon|(sars-cov-2|covid-19) variant|novel coronavirus|novel virus)"),
    ("Infrastructure", r"\b(critical infrastructure|power grid|blackout|outage|cascading failure|grid resilience|water supply|undersea cable|submarine cable|pipeline|supply chain disruption|gnss|gps spoofing|gps jamming|satellite)"),
    ("Space weather", r"\b(space weather|geomagnetic storm|solar flare|coronal mass ejection|cme\b|solar energetic particle|ionospheric|substorm)"),
    ("Security", r"\b(terroris|armed conflict|missile|drone strike|uav swarm|nuclear weapon|nuclear security|radiological|chemical weapon|hybrid warfare|disinformation|deepfake|mass surveillance|border security|extremis)"),
    ("Technology", r"\b(ai safety|frontier ai|large language model.{0,40}(risk|misuse|attack|safety)|autonomous weapon|quantum (cryptanalysis|computing.{0,20}(threat|break))|post-quantum)"),
    ("Hazards", r"\b(earthquake early warning|tsunami|volcan|wildfire|hurricane|tropical cyclone|flood forecast|extreme heat|landslide)"),
]
RX_TOPICS = [(n, re.compile(p, re.I)) for n, p in RESEARCH_TOPICS]
RX_RETRO = re.compile(r"\b(during|after|amid|in) (the )?covid(-19)?( pandemic)?|post[- ]covid|pandemic era|covid-19 pandemic|students|nurses|education", re.I)
RX_JUNK = re.compile(r"^(review \d|reply|response to|comment on|erratum|correction|retraction)|youtube|blueprint|narrative & production|\bv\d+(\.\d+)? [—-]", re.I)
JUNK_VENUES = {"zenodo", "figshare", "researchgate", "qeios", "osf preprints", "authorea", "preprints.org", "ssrn electronic journal"}
def research_tags(text):
    if not text or RX_JUNK.search(text): return []
    tags = [n for n, rx in RX_TOPICS if rx.search(text)]
    if tags == ["Disease"] and RX_RETRO.search(text): return []     # retrospective "during the COVID-19 pandemic" papers are not outbreak research
    return tags

WATCH_APPLICANTS = [
    # defense / aerospace
    ("Lockheed Martin", r"lockheed"), ("RTX / Raytheon", r"raytheon|\brtx corp|pratt ?& ?whitney|collins aerospace"), ("Northrop Grumman", r"northrop"),
    ("Boeing", r"\bboeing\b"), ("General Dynamics", r"general dynamics"), ("BAE Systems", r"\bbae systems"), ("L3Harris", r"l3harris|harris corp"),
    ("Thales", r"\bthales\b"), ("Airbus", r"\bairbus\b"), ("Leonardo", r"\bleonardo s\.?p\.?a"), ("Rheinmetall", r"rheinmetall"), ("Saab", r"\bsaab ab\b"),
    ("MBDA", r"\bmbda\b"), ("Safran", r"\bsafran\b"), ("Anduril", r"anduril"), ("Palantir", r"palantir"), ("SpaceX", r"space exploration technologies"),
    # tech
    ("Google / Alphabet", r"\bgoogle\b|deepmind|waymo|\bx development\b"), ("Apple", r"\bapple inc"), ("Microsoft", r"microsoft"), ("Nvidia", r"nvidia"),
    ("IBM", r"international business machines|\bibm\b"), ("Intel", r"\bintel corp"), ("AMD", r"advanced micro devices"), ("Qualcomm", r"qualcomm"),
    ("Meta", r"meta platforms"), ("Amazon", r"amazon (technologies|\.com)"), ("OpenAI", r"\bopenai\b"), ("Samsung", r"samsung electronics"),
    ("TSMC", r"taiwan semiconductor manufacturing"), ("Huawei", r"huawei"), ("Tesla", r"\btesla,? inc"), ("Siemens", r"\bsiemens\b(?! energy| healthineers)"),
    ("Cisco", r"cisco technology|cisco systems"), ("Ericsson", r"ericsson"), ("Nokia", r"\bnokia\b"), ("Sony", r"\bsony group|sony semiconductor"),
    # biotech / pharma
    ("Pfizer", r"\bpfizer"), ("Moderna", r"moderna"), ("BioNTech", r"biontech"), ("Johnson & Johnson / Janssen", r"johnson ?& ?johnson|janssen"),
    ("Merck / MSD", r"merck sharp|merck patent|\bmerck & co"), ("Novartis", r"novartis"), ("Roche", r"hoffmann-la roche|genentech|\broche\b"),
    ("AstraZeneca", r"astrazeneca"), ("GSK", r"glaxosmithkline|\bgsk\b"), ("Sanofi", r"\bsanofi"), ("Gilead", r"gilead"), ("Regeneron", r"regeneron"),
    ("Eli Lilly", r"eli lilly"), ("Novo Nordisk", r"novo nordisk"), ("Illumina", r"illumina"), ("CSL / Seqirus", r"seqirus|\bcsl behring"),
    # energy
    ("ExxonMobil", r"exxon ?mobil"), ("Chevron", r"chevron"), ("Shell", r"\bshell (internationale|oil|usa)"), ("BP", r"\bbp (p\.?l\.?c|exploration|corporation)"),
    ("TotalEnergies", r"totalenergies"), ("Saudi Aramco", r"aramco"), ("SLB / Schlumberger", r"schlumberger"), ("Halliburton", r"halliburton"),
    ("GE / GE Vernova", r"general electric|ge vernova|ge infrastructure"), ("Siemens Energy", r"siemens energy|siemens gamesa"), ("Hitachi Energy", r"hitachi energy"),
    ("Westinghouse", r"westinghouse electric"), ("Framatome", r"framatome"), ("Vestas", r"\bvestas"), ("CATL", r"contemporary amperex"),
]
RX_APPL = [(n, re.compile(p, re.I)) for n, p in WATCH_APPLICANTS]
PATENT_SECTOR = {**{n: "Defense / aerospace" for n, _ in WATCH_APPLICANTS[:17]}, **{n: "Technology" for n, _ in WATCH_APPLICANTS[17:37]},
                 **{n: "Biotech / pharma" for n, _ in WATCH_APPLICANTS[37:53]}, **{n: "Energy" for n, _ in WATCH_APPLICANTS[53:]}}

RX_BILLION = re.compile(r"(?:\$|US\$|USD ?|€|£|EUR ?|GBP ?)\s?(\d{1,4}(?:[.,]\d{1,3})?)\s?(billion|bn|b\b|trillion|tn)", re.I)
RX_DEAL = re.compile(r"\b(acquir|acquisition|merger|merge[sd]?\b|takeover|buyout|buy-out|buys\b|to buy|agrees to buy|snaps up|purchase of|tender offer|bid for|takeover bid|deal to (buy|acquire)|combine with|to sell .{0,60} for)", re.I)
RX_STRATEGIC = re.compile(r"\b(defen[cs]e|energy|power generation|power plant|missile|munition|aerospace|shipbuild|semiconductor|chipmaker|nuclear|uranium|grid|utility|pipeline|lng|port operator|telecom|undersea cable|satellite|cybersecurity|rare earth|critical mineral)", re.I)
def deal_value_b(t):
    best = None
    for m in RX_BILLION.finditer(t or ""):
        v = float(m.group(1).replace(",", ".")) * (1000 if m.group(2).lower() in ("trillion", "tn") else 1)
        best = max(best or 0, v)
    return best

# ------------------------------------------------------------------ source registry (also feeds the Sources page; grade = editorial start, visitors move it)
SOURCES = [
 # key, stream, name, url, type, category, start rating 0-10, why, profile
 ("OpenAlex API", "research", "OpenAlex (research works API)", "https://openalex.org/", "Research center", "cyber", 8, "open scholarly index run by the nonprofit OurResearch; metadata comes from publishers/Crossref",
  "Free, keyless index of 250M+ scholarly works (successor to Microsoft Academic). Queried for new papers on threats, security, disease, infrastructure, space weather and AI risk. Stand-in for Google Scholar, which has no API and forbids automated access."),
 ("arXiv RSS", "research", "arXiv preprints (RSS: cs.CR, physics.space-ph, q-bio.PE, eess.SY)", "https://arxiv.org/", "Research center", "cyber", 7, "Cornell-run preprint server; moderated but not peer reviewed",
  "Daily new-submission feeds for cryptography & security, space physics, populations & evolution (epidemics) and systems & control (infrastructure). Preprints are not peer reviewed."),
 ("PubMed E-utilities", "research", "PubMed (NCBI E-utilities)", "https://pubmed.ncbi.nlm.nih.gov/", "Agency feed", "disease", 9, "U.S. National Library of Medicine index of peer-reviewed biomedical literature",
  "Official NLM/NCBI index. Searched for new papers on outbreaks, emerging pathogens, avian influenza, antimicrobial resistance and biosecurity."),
 ("medRxiv / bioRxiv API", "research", "medRxiv and bioRxiv preprints (api.biorxiv.org)", "https://www.medrxiv.org/", "Research center", "disease", 6, "Cold Spring Harbor preprint servers; screened, not peer reviewed",
  "New health-science and biology preprints in infectious disease, epidemiology, public health and microbiology. Not peer reviewed; findings can change."),
 ("WikiLeaks releases", "leaks", "WikiLeaks release listing (wikileaks.org)", "https://wikileaks.org/-Leaks-.html", "Other", "political", 6, "primary-document publisher; documents are usually authentic but selection and framing are editorial",
  "The site's own release listing and news page, checked every cycle. Any release newer than the last one on record is flagged as new. Documents are published as-is; their context needs independent reporting."),
 ("EPO Publication Server", "patents", "European Patent Office Publication Server (data.epo.org)", "https://data.epo.org/publication-server/", "Agency feed", "financial", 10, "official European Patent Office publication service",
  "Official weekly European patent publications (applications and grants), read keyless. Filtered to a watch list of major defense, technology, biotech and energy applicants."),
 ("SEC EDGAR full-text search", "mna", "SEC EDGAR full-text search (efts.sec.gov)", "https://efts.sec.gov/LATEST/search-index?q=&forms=SC%20TO-T", "Agency feed", "financial", 10, "official U.S. Securities and Exchange Commission filings",
  "Official U.S. filings that signal takeovers and mergers: tender offers (SC TO-T), target responses (SC 14D9), merger proxies (DEFM14A/PREM14A) and merger registrations (S-4/F-4)."),
 ("PR Newswire M&A", "mna", "PR Newswire — acquisitions, mergers and takeovers (RSS)", "https://www.prnewswire.com/news-releases/financial-services-latest-news/acquisitions-mergers-and-takeovers-list/", "RSS feed", "financial", 5, "company press releases: primary statements of the deal parties, promotional by nature",
  "Official deal announcements as released by the companies. Kept only when the headline names a deal of $1 billion or more, or a defense / critical-infrastructure deal."),
 ("Guardian M&A", "mna", "The Guardian — mergers and acquisitions (RSS)", "https://www.theguardian.com/business/mergers-and-acquisitions", "News outlet", "financial", 7, "major UK newspaper",
  "Guardian business desk coverage of mergers and takeovers, filtered by the same deal-size / strategic rule."),
 ("Yahoo Finance chart API", "markets", "Yahoo Finance chart API (delayed quotes)", "https://finance.yahoo.com/", "Agency feed", "financial", 7, "widely used delayed market data; exchange-sourced but unofficial",
  "Daily moves for 16 world stock indexes, 14 currency pairs, the dollar index, oil, gas, gold, copper, Bitcoin, the VIX and the U.S. 10-year yield. Items appear only when a move passes a fixed threshold."),
 ("FDIC bank failures API", "markets", "FDIC failed banks (api.fdic.gov)", "https://www.fdic.gov/bank-failures/failed-bank-list", "Agency feed", "financial", 10, "official Federal Deposit Insurance Corporation data",
  "Official list of U.S. bank failures with date, location, assets and estimated cost to the Deposit Insurance Fund."),
 ("Federal Reserve press (monetary policy)", "markets", "Federal Reserve monetary policy releases (RSS)", "https://www.federalreserve.gov/feeds/press_monetary.xml", "Agency feed", "financial", 10, "official central bank",
  "FOMC statements, rate decisions, minutes and other monetary policy press releases."),
 ("ECB press releases", "markets", "European Central Bank press releases (RSS)", "https://www.ecb.europa.eu/rss/press.html", "Agency feed", "financial", 10, "official central bank",
  "ECB press releases; monetary policy decisions, rate changes and financial-stability items are surfaced."),
 ("Bank of England news", "markets", "Bank of England news (RSS)", "https://www.bankofengland.co.uk/rss/news", "Agency feed", "financial", 10, "official central bank",
  "Bank of England news; Bank Rate decisions, Monetary Policy Summaries and financial-stability items are surfaced."),
 ("Bank of Japan what's new", "markets", "Bank of Japan what's new (RSS)", "https://www.boj.or.jp/en/rss/whatsnew.xml", "Agency feed", "financial", 10, "official central bank",
  "Bank of Japan releases; monetary policy statements and market operations notices are surfaced."),
 ("BLS latest releases", "markets", "U.S. Bureau of Labor Statistics latest releases (RSS)", "https://www.bls.gov/feed/bls_latest.rss", "Agency feed", "financial", 10, "official U.S. statistics agency",
  "Release of record for jobs (Employment Situation), inflation (CPI, PPI) and other U.S. labor indicators."),
 ("BEA releases", "markets", "U.S. Bureau of Economic Analysis releases (RSS)", "https://apps.bea.gov/rss/rss.xml", "Agency feed", "financial", 10, "official U.S. statistics agency",
  "Release of record for U.S. GDP, personal income and outlays (PCE inflation), trade balance and related indicators."),
 ("BBC Business", "markets", "BBC News — business (RSS)", "https://www.bbc.co.uk/news/business", "News outlet", "financial", 8, "public broadcaster",
  "BBC business headlines, kept only when they report a bank failure, currency crisis, market crash, emergency rate move or default."),
 ("Guardian Business", "markets", "The Guardian — business (RSS)", "https://www.theguardian.com/business", "News outlet", "financial", 7, "major UK newspaper",
  "Guardian business headlines, same market-shock filter."),
 ("CNBC Finance", "markets", "CNBC — finance (RSS)", "https://www.cnbc.com/finance/", "News outlet", "financial", 7, "U.S. business broadcaster",
  "CNBC finance headlines, same market-shock filter."),
 ("MarketWatch", "markets", "MarketWatch — top stories (RSS)", "https://www.marketwatch.com/", "News outlet", "financial", 7, "Dow Jones market news site",
  "MarketWatch top stories, same market-shock filter."),
 ("DW Business", "markets", "DW — business (RSS)", "https://www.dw.com/en/business/s-1431", "News outlet", "financial", 8, "German public international broadcaster",
  "Deutsche Welle business headlines (global coverage), same market-shock filter."),
]
SOURCE_BY_KEY = {s[0]: s for s in SOURCES}
CAT_FOR = {"research": "cyber", "leaks": "political", "patents": "financial", "mna": "financial", "markets": "financial"}

# ------------------------------------------------------------------ item intake (dedupe 12 h, link check, insert)
class Run:
    def __init__(self, c): self.c = c; self.stats = {}
    def add(self, stream, source, title, url, published=None, summary="", tags=None, extra=None, check=True):
        title = clean(title, 300); url = re.sub(r"^(https?://[^/]+)//+", r"\1/", (url or "").strip())
        if url.startswith("http://www.boj.or.jp/"): url = "https://" + url[7:]
        st = self.stats.setdefault(source, {"stream": stream, "new": 0, "seen": 0, "rejected": 0})
        if not title or not url: return False
        iid = hashlib.sha1(url.encode()).hexdigest()[:20]
        if self.c.execute("SELECT 1 FROM items WHERE id=?", (iid,)).fetchone() or self.c.execute("SELECT 1 FROM rejected WHERE url=? AND ts>?", (url, iso(now() - timedelta(days=2)))).fetchone():
            st["seen"] += 1; return False
        k = tkey(title); cut = iso(now() - timedelta(hours=DEDUPE_H))
        if self.c.execute("SELECT 1 FROM items WHERE tkey=? AND stream=? AND found>=?", (k, stream, cut)).fetchone(): st["seen"] += 1; return False
        ok, code, note = check_link(url) if check else (True, 200, "")
        if not ok:
            st["rejected"] += 1
            if code in (0, 429, 500, 502, 503, 504): return False      # transient: try again next cycle
            self.c.execute("INSERT OR REPLACE INTO rejected VALUES(?,?,?,?,?)", (url, stream, title, f"{code} {note}", iso())); self.c.commit(); return False
        if not published or published > iso(): published = iso()     # journal issue dates can be in the future: never list an item ahead of now
        self.c.execute("INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (iid, stream, source, title, url, published, iso(), clean(summary, 600),
                       json.dumps(tags or []), json.dumps(extra or {}), k, code, note)); self.c.commit()
        st["new"] += 1; return True
    def run_source(self, source, fn):
        stream = SOURCE_BY_KEY[source][1]; t0 = time.time(); err = None
        try: fn()
        except Exception as ex: err = f"{type(ex).__name__}: {str(ex)[:200]}"; log(f"{source}: {err}")
        s = self.stats.setdefault(source, {"stream": stream, "new": 0, "seen": 0, "rejected": 0})
        self.c.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?)", (source, stream, iso(), 0 if err else 1, s["new"], s["seen"], err)); self.c.commit()
        log(f"{source}: new={s['new']} seen={s['seen']} rejected={s['rejected']} {'ERR ' + err if err else ''} ({time.time() - t0:.0f}s)")

def due(c, key, every_s):
    last = sget(c, "due:" + key, 0)
    if time.time() - last < every_s: return False
    sset(c, "due:" + key, time.time()); c.commit(); return True

# ------------------------------------------------------------------ stream 1: research
def research(R):
    c = R.c; d0 = (now() - timedelta(days=3)).strftime("%Y-%m-%d"); today = now().strftime("%Y-%m-%d")
    def openalex():
        qs = ["cyberattack OR ransomware OR malware OR \"zero-day\"", "outbreak OR pandemic OR \"avian influenza\" OR \"emerging infectious\"",
              "\"critical infrastructure\" OR \"power grid\" OR \"submarine cable\"", "\"space weather\" OR \"geomagnetic storm\" OR \"solar flare\"",
              "terrorism OR \"armed conflict\" OR \"nuclear security\" OR deepfake", "\"AI safety\" OR \"autonomous weapons\" OR \"post-quantum\""]
        errs = []
        for q in qs:
            try: j = getjson("https://api.openalex.org/works?" + urllib.parse.urlencode({"search": q, "filter": f"from_publication_date:{d0},to_publication_date:{today},type:article|preprint",
                        "per_page": 15, "select": "id,doi,display_name,publication_date,primary_location,authorships,type", "mailto": MAILTO}), timeout=45)
            except Exception as ex:
                errs.append(f"{q[:30]}: {type(ex).__name__}"); continue
            for w in j.get("results") or []:
                t = w.get("display_name") or ""; tags = research_tags(t)
                if not tags: continue
                loc = w.get("primary_location") or {}; src = ((loc.get("source") or {}).get("display_name")) or ""
                if not src or any(j in src.lower() for j in JUNK_VENUES) or len(t) > 240: continue      # self-deposits without a journal/preprint venue are skipped
                url = w.get("doi") or loc.get("landing_page_url") or w.get("id")
                au = ", ".join((a.get("author") or {}).get("display_name", "") for a in (w.get("authorships") or [])[:3])
                R.add("research", "OpenAlex API", t, url, (w.get("publication_date") or "") + "T00:00:00Z", f"{src}{' · ' if src and au else ''}{au}", tags,
                      {"venue": src, "type": w.get("type"), "openalex": w.get("id")})
            time.sleep(1)
        if len(errs) == len(qs): raise RuntimeError("; ".join(errs))
    def arxiv():
        for cat in ("cs.CR", "physics.space-ph", "q-bio.PE", "eess.SY"):
            for x in rss(f"https://rss.arxiv.org/rss/{cat}", 400):
                if "Announce Type: new" not in x["summary"] and "Announce Type: cross" not in x["summary"]: continue
                text = x["title"] + " " + x["summary"]; tags = research_tags(x["title"]) or (research_tags(text) if cat != "cs.CR" else [])
                if cat == "cs.CR" and not tags: continue
                if not tags: continue
                summ = re.sub(r"^arXiv:\S+\s+Announce Type: \w+\s+Abstract:\s*", "", x["summary"])
                R.add("research", "arXiv RSS", x["title"], x["url"].replace("http://", "https://"), x["time"], summ[:400], tags, {"category": cat, "peer_reviewed": False})
            time.sleep(3)
    def pubmed():
        term = ('(outbreak[tiab] OR pandemic[tiab] OR epidemic[tiab] OR "avian influenza"[tiab] OR H5N1[tiab] OR mpox[tiab] OR ebola[tiab] OR marburg[tiab] OR '
                'nipah[tiab] OR "antimicrobial resistance"[tiab] OR biosecurity[tiab] OR bioterrorism[tiab] OR "emerging infectious"[tiab] OR zoonotic[tiab]) AND "last 3 days"[edat]')
        j = getjson("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "term": term, "retmode": "json", "retmax": 40, "sort": "pub_date", "tool": "blackout.network", "email": MAILTO}))
        ids = (j.get("esearchresult") or {}).get("idlist") or []
        if not ids: return
        time.sleep(0.5)
        s = getjson("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json", "tool": "blackout.network", "email": MAILTO}))
        res = s.get("result") or {}
        for pid in ids:
            r = res.get(pid) or {}; t = clean(r.get("title"), 300)
            tags = research_tags(t)
            if not tags: continue                                   # the title itself must be on-topic
            au = ", ".join(a.get("name", "") for a in (r.get("authors") or [])[:3])
            R.add("research", "PubMed E-utilities", t, f"https://pubmed.ncbi.nlm.nih.gov/{pid}/", pdate(r.get("sortpubdate", "").replace("/", "-")[:10]) or iso(),
                  f"{r.get('fulljournalname') or r.get('source') or ''} · {au}", tags, {"pmid": pid, "peer_reviewed": True})
    def rxiv():
        cats = {"medrxiv": {"infectious diseases", "epidemiology", "public and global health"}, "biorxiv": {"microbiology", "epidemiology"}}
        d1 = (now() - timedelta(days=2)).strftime("%Y-%m-%d")
        for server, keep in cats.items():
            cursor = 0
            for _ in range(4):
                j = getjson(f"https://api.biorxiv.org/details/{server}/{d1}/{today}/{cursor}")
                col = j.get("collection") or []
                for p in col:
                    if (p.get("category") or "").lower() not in keep: continue
                    t = p.get("title") or ""; tags = research_tags(t)
                    if not tags: continue
                    R.add("research", "medRxiv / bioRxiv API", t, f"https://doi.org/{p['doi']}", (p.get("date") or "") + "T00:00:00Z",
                          f"{server} · {p.get('category')} · {(p.get('authors') or '')[:120]}", tags, {"server": server, "peer_reviewed": False, "doi": p.get("doi")})
                cursor += len(col)
                if len(col) < 100: break
                time.sleep(1)
    for name, fn in (("OpenAlex API", openalex), ("arXiv RSS", arxiv), ("PubMed E-utilities", pubmed), ("medRxiv / bioRxiv API", rxiv)): R.run_source(name, fn)

# ------------------------------------------------------------------ stream 2: WikiLeaks
def leaks(R):
    def wl():
        c = R.c
        h = http("https://wikileaks.org/-Leaks-.html", accept="text/html").decode("utf-8", "replace")
        rel = []
        for m in re.finditer(r'<li class="tile">\s*<a href="([^"]+)">(.*?)</li>', h, re.S):
            href, body = m.group(1), m.group(2)
            t = re.search(r'<h2 class="title">(.*?)</h2>', body, re.S); ts = re.search(r'<div class="timestamp[^"]*">(.*?)</div>', body, re.S)
            it = re.search(r'<div class="intro">(.*?)</div>', body, re.S)
            if t: rel.append({"title": clean(t.group(1)), "url": urllib.parse.urljoin("https://wikileaks.org/", href.replace("org//", "org/")),
                              "date": pdate(clean(ts.group(1))) if ts else None, "intro": clean(it.group(1)) if it else ""})
        n = http("https://wikileaks.org/-News-.html", accept="text/html").decode("utf-8", "replace")
        news = []
        for m in re.finditer(r'<h3 class="title"><a href="([^"]+)">(.*?)</a></h3>\s*<div class="timestamp">(.*?)</div>', n, re.S):
            news.append({"title": clean(m.group(2)), "url": urllib.parse.urljoin("https://wikileaks.org/", m.group(1)), "date": pdate(clean(m.group(3)))})
        if not rel: raise RuntimeError("release listing parsed 0 entries (page layout changed?)")
        rel.sort(key=lambda x: x["date"] or "", reverse=True); news.sort(key=lambda x: x["date"] or "", reverse=True)
        prev = sget(c, "wl_latest"); prev_news = sget(c, "wl_latest_news")
        baseline = prev is None
        for x in rel:
            if baseline: break
            if (x["date"] or "") > (prev or {}).get("date", "") or x["url"] not in sget(c, "wl_urls", []):
                R.add("leaks", "WikiLeaks releases", "New WikiLeaks release: " + x["title"], x["url"], x["date"], x["intro"], ["Release", "NEW"], {"kind": "release"})
        for x in news:
            if prev_news is None: break
            if (x["date"] or "") > (prev_news or {}).get("date", ""):
                R.add("leaks", "WikiLeaks releases", "WikiLeaks statement: " + x["title"], x["url"], x["date"], "", ["Statement"], {"kind": "news"})
        sset(c, "wl_latest", rel[0]); sset(c, "wl_latest_news", news[0] if news else None); sset(c, "wl_urls", [x["url"] for x in rel])
        sset(c, "wl_checked", {"ts": iso(), "releases_listed": len(rel), "news_listed": len(news), "baseline_run": baseline}); c.commit()
    R.run_source("WikiLeaks releases", wl)

# ------------------------------------------------------------------ stream 3: patents (EPO Publication Server)
EPO = "https://data.epo.org/publication-server/rest/v1.2"
def patents(R, budget=700, workers=3):
    def epo():
        c = R.c
        dates = re.findall(r"publication-dates/(\d{8})/patents", http(EPO + "/publication-dates", accept="text/html").decode())
        weeks = sorted(set(dates), reverse=True)[:2]
        left = budget
        for wk in weeks:
            if left <= 0: break
            done = sget(c, "epo_done:" + wk, False)
            if done: continue
            pns = re.findall(r"/patents/(EP\w+)\"", http(f"{EPO}/publication-dates/{wk}/patents", accept="text/html").decode())
            seen = {r[0] for r in c.execute("SELECT pn FROM epo_seen WHERE week=?", (wk,))}
            todo = [p for p in pns if p not in seen][:left]
            def one(pn):
                for attempt in range(2):
                    try:
                        x = http(f"{EPO}/patents/{pn}/document.xml", accept="application/xml", headers={"Range": "bytes=0-14000"}, timeout=30).decode("utf-8", "replace")
                        break
                    except Exception as ex:
                        if attempt: return pn, None, None, str(ex)[:80]
                        time.sleep(2)
                appl = "; ".join(clean(a) for a in re.findall(r"<B711>.*?<snm>(.*?)</snm>", x, re.S)[:4])
                tm = re.search(r"<B541>en</B541>\s*<B542>(.*?)</B542>", x, re.S)
                return pn, appl, clean(tm.group(1)) if tm else "", None
            with cf.ThreadPoolExecutor(workers) as ex:
                for k, (pn, appl, title, err) in enumerate(ex.map(one, todo)):
                    if k % 100 == 0: sset(c, "epo_progress", {"week": wk, "processed": len(seen) + k, "total": len(pns), "ts": iso()}); c.commit()
                    if err: continue
                    hit = [n for n, rx in RX_APPL if appl and rx.search(appl)]
                    c.execute("INSERT OR REPLACE INTO epo_seen VALUES(?,?,?,?,?,?)", (pn, wk, appl, title, ",".join(hit), iso())); c.commit()
                    if hit:
                        m = re.match(r"EP(\d+)\w{2}([AB]\d)$", pn); num, kind = (m.group(1), m.group(2)) if m else (pn, "")
                        label = "granted patent" if kind.startswith("B") else "patent application"
                        sect = PATENT_SECTOR.get(hit[0], "")
                        R.add("patents", "EPO Publication Server", f"{hit[0]}: {title.capitalize() if title.isupper() else title}", f"{EPO}/patents/{pn}/document.html",
                              f"{wk[:4]}-{wk[4:6]}-{wk[6:]}T00:00:00Z", f"European {label} EP {num} {kind} · applicant: {appl}", [sect, hit[0]],
                              {"pn": f"EP{num}{kind}", "applicant": appl, "kind": label, "espacenet": f"https://worldwide.espacenet.com/patent/search?q=pn%3DEP{num}{kind}"})
            c.commit(); left -= len(todo)
            if len(todo) and len(seen) + len(todo) >= len(pns): sset(c, "epo_done:" + wk, True); c.commit()
            sset(c, "epo_progress", {"week": wk, "processed": len(seen) + len(todo), "total": len(pns), "ts": iso()}); c.commit()
    R.run_source("EPO Publication Server", epo)

# ------------------------------------------------------------------ stream 4: M&A
SEC_FORMS = {"SC TO-T": "tender offer (takeover bid)", "SC 14D9": "target company's response to a tender offer", "DEFM14A": "definitive merger proxy",
             "PREM14A": "preliminary merger proxy", "DEFM14C": "merger information statement", "S-4": "merger registration statement", "F-4": "merger registration statement (foreign issuer)"}
def mna(R):
    def edgar():
        d0 = (now() - timedelta(days=3)).strftime("%Y-%m-%d"); d1 = now().strftime("%Y-%m-%d")
        j = getjson("https://efts.sec.gov/LATEST/search-index?" + urllib.parse.urlencode({"forms": ",".join(SEC_FORMS), "dateRange": "custom", "startdt": d0, "enddt": d1}), ua=SEC_UA)
        seen = set()
        for hh in (j.get("hits") or {}).get("hits") or []:
            s = hh.get("_source") or {}; form = s.get("form") or s.get("root_form") or ""
            if form not in SEC_FORMS: continue           # amendments (/A) are left out
            adsh = s.get("adsh") or hh["_id"].split(":")[0]
            if adsh in seen: continue
            seen.add(adsh)
            ciks = s.get("ciks") or []; names = [re.sub(r"\s+\(CIK \d+\)", "", re.sub(r"\s{2,}", " ", n)).strip() for n in s.get("display_names") or []]
            if not ciks: continue
            url = f"https://www.sec.gov/Archives/edgar/data/{int(ciks[0])}/{adsh.replace('-', '')}/{adsh}-index.htm"
            who = " / ".join(names[:3])
            title = f"{form}: {who}" + (" — tender offer" if form == "SC TO-T" else " — merger" if form in ("DEFM14A", "PREM14A", "DEFM14C", "S-4", "F-4") else "")
            R.add("mna", "SEC EDGAR full-text search", title, url, (s.get("file_date") or d1) + "T00:00:00Z", f"SEC {form}: {SEC_FORMS[form]}. Filed {s.get('file_date')}. Deal terms are in the filing.",
                  ["SEC filing", form], {"form": form, "adsh": adsh, "companies": names})
            time.sleep(0.15)
    def news_fn(name, url):
        def f():
            for x in rss(url, 60):
                t = x["title"]
                if not x["time"] or now() - datetime.fromisoformat(x["time"].replace("Z", "+00:00")) > timedelta(days=3): continue
                if not RX_DEAL.search(t): continue
                v = deal_value_b(t); strat = RX_STRATEGIC.search(t)
                if not ((v is not None and v >= 1) or strat): continue
                tags = ["News"] + ([f"${v:g}B" if v < 1000 else f"${v/1000:g}T"] if v else []) + (["Strategic"] if strat else [])
                R.add("mna", name, t, x["url"], x["time"], x["summary"][:300], tags, {"value_b": v})
        return f
    R.run_source("SEC EDGAR full-text search", edgar)
    for name, url in (("PR Newswire M&A", "https://www.prnewswire.com/rss/financial-services-latest-news/acquisitions-mergers-and-takeovers-list.rss"),
                      ("Guardian M&A", "https://www.theguardian.com/business/mergers-and-acquisitions/rss")):
        R.run_source(name, news_fn(name, url))

# ------------------------------------------------------------------ stream 5: markets
MKT = [  # symbol, label, kind, threshold (% unless kind == 'yield' -> absolute points)
 ("^GSPC", "S&P 500", "index", 3), ("^DJI", "Dow Jones", "index", 3), ("^IXIC", "Nasdaq Composite", "index", 3), ("^RUT", "Russell 2000", "index", 3),
 ("^GSPTSE", "S&P/TSX (Canada)", "index", 3), ("^BVSP", "Bovespa (Brazil)", "index", 3), ("^FTSE", "FTSE 100 (UK)", "index", 3), ("^GDAXI", "DAX (Germany)", "index", 3),
 ("^FCHI", "CAC 40 (France)", "index", 3), ("^STOXX50E", "Euro Stoxx 50", "index", 3), ("^N225", "Nikkei 225 (Japan)", "index", 3), ("^HSI", "Hang Seng (Hong Kong)", "index", 3),
 ("000001.SS", "Shanghai Composite", "index", 3), ("^KS11", "KOSPI (South Korea)", "index", 3), ("^BSESN", "Sensex (India)", "index", 3), ("^AXJO", "ASX 200 (Australia)", "index", 3),
 ("EURUSD=X", "EUR/USD", "fx", 2), ("JPY=X", "USD/JPY", "fx", 2), ("GBPUSD=X", "GBP/USD", "fx", 2), ("CNY=X", "USD/CNY", "fx", 2), ("CHF=X", "USD/CHF", "fx", 2),
 ("INR=X", "USD/INR", "fx", 2), ("KRW=X", "USD/KRW", "fx", 2), ("MXN=X", "USD/MXN", "fx", 2), ("BRL=X", "USD/BRL", "fx", 2), ("TRY=X", "USD/TRY", "fx", 2),
 ("ZAR=X", "USD/ZAR", "fx", 2), ("AUDUSD=X", "AUD/USD", "fx", 2), ("CAD=X", "USD/CAD", "fx", 2), ("ARS=X", "USD/ARS", "fx", 2), ("DX-Y.NYB", "U.S. Dollar Index", "fx", 1.5),
 ("CL=F", "WTI crude oil", "commodity", 5), ("BZ=F", "Brent crude oil", "commodity", 5), ("NG=F", "U.S. natural gas", "commodity", 8), ("GC=F", "Gold", "commodity", 3),
 ("HG=F", "Copper", "commodity", 4), ("BTC-USD", "Bitcoin", "crypto", 8), ("^VIX", "VIX volatility index", "vix", 25), ("^TNX", "U.S. 10-year Treasury yield", "yield", 0.15),
]
RX_MKT_NEWS = re.compile(r"\bbanks? (failure|fails|failed|collapse|collapses|run|seized|closed by regulators|shut)|\b(bank run|bank collapse|bank failure)\b|"
    r"\b(currenc(y|ies)|naira|rupee|peso|lira|rand|ruble|rouble|yen|yuan|won|real|cedi|shilling|pound|euro|dollar)\b.{0,40}\b(devaluation|devalued|slump|plunge|plunges|collapse|collapses|crisis|record low|free fall|freefall)|"
    r"\bdevalu|\b(stocks?|shares|markets?|index|indexes|wall street|nasdaq|dow|s&p 500|nikkei|kospi|sensex)\b.{0,40}\b(plunge|plunges|crash|crashes|tumble|tumbles|worst day since|sell-off|rout)|"
    r"circuit breaker|trading (halt|halted|suspended)|emergency rate|surprise rate (hike|cut)|sovereign default|defaults? on (its )?(debt|bonds)|raise[sd]? interest rates", re.I)
def markets(R):
    def quotes():
        c = R.c
        for i in range(0, len(MKT), 1):
            sym, label, kind, thr = MKT[i]
            try: j = getjson(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=1d&interval=1d")
            except Exception:
                time.sleep(1); j = getjson(f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=1d&interval=1d")
            m = ((j.get("chart") or {}).get("result") or [{}])[0].get("meta") or {}
            px, prev, t = m.get("regularMarketPrice"), m.get("chartPreviousClose") or m.get("previousClose"), m.get("regularMarketTime")
            if not px or not prev or not t: continue
            day = datetime.fromtimestamp(t, timezone.utc)
            if now() - day > timedelta(hours=36): continue      # stale quote (weekend/holiday): nothing new
            pct = (px - prev) / prev * 100; diff = px - prev
            hit = (abs(diff) >= thr) if kind == "yield" else (pct >= thr or (px >= 30 and prev < 30)) if kind == "vix" else abs(pct) >= thr
            if not hit: continue
            what = (f"{'up' if diff > 0 else 'down'} {abs(diff) * 100:.0f} bp to {px:.2f}%" if kind == "yield" else f"{'+' if pct > 0 else '−'}{abs(pct):.1f}% to {px:,.2f}")
            url = "https://finance.yahoo.com/quote/" + urllib.parse.quote(sym, safe="") + "/"
            R.add("markets", "Yahoo Finance chart API", f"{label} {what}", url + f"?bn={day:%Y%m%d}", iso(day),
                  f"Previous close {prev:,.4g}; threshold {'±%g bp' % (thr * 100) if kind == 'yield' else ('+%g%% or a close above 30' % thr if kind == 'vix' else '±%g%%' % thr)}. Delayed quote.",
                  ["Market move", kind], {"symbol": sym, "pct": round(pct, 2), "price": px, "prev": prev})
            time.sleep(0.4)
    def fdic():
        j = getjson("https://api.fdic.gov/banks/failures?" + urllib.parse.urlencode({"limit": 10, "sort_by": "FAILDATE", "sort_order": "DESC", "fields": "NAME,CITYST,FAILDATE,COST,QBFASSET,QBFDEP,CERT,RESTYPE1,SAVR"}))
        for r in j.get("data") or []:
            d = r.get("data") or {}
            try: fd = datetime.strptime(d.get("FAILDATE", ""), "%m/%d/%Y").replace(tzinfo=timezone.utc)
            except Exception: continue
            if now() - fd > timedelta(days=120): continue
            assets = d.get("QBFASSET"); cost = d.get("COST")
            R.add("markets", "FDIC bank failures API", f"Bank failure: {d.get('NAME')} ({d.get('CITYST')})", f"https://www.fdic.gov/bank-failures/failed-bank-list#cert{d.get('CERT')}",
                  iso(fd), f"Closed {fd:%b %d, %Y}." + (f" Total assets about ${assets/1000:,.0f}M." if assets else "") + (f" Estimated cost to the Deposit Insurance Fund ${cost/1000:,.0f}M." if cost else ""),
                  ["Bank failure"], {"cert": d.get("CERT")})
    CB = [("Federal Reserve press (monetary policy)", "https://www.federalreserve.gov/feeds/press_monetary.xml", None),
          ("ECB press releases", "https://www.ecb.europa.eu/rss/press.html", r"monetary policy|interest rate|key ecb|financial stability|emergency|liquidity|banking supervision.{0,30}(decision|failing)"),
          ("Bank of England news", "https://www.bankofengland.co.uk/rss/news", r"bank rate|monetary policy|financial stability|financial policy"),
          ("Bank of Japan what's new", "https://www.boj.or.jp/en/rss/whatsnew.xml", r"monetary policy|statement on|outlook for economic|market operations"),
          ("BLS latest releases", "https://www.bls.gov/feed/bls_latest.rss", r"employment situation|consumer price|producer price|job openings|real earnings|import and export price|employment cost|productivity"),
          ("BEA releases", "https://apps.bea.gov/rss/rss.xml", r"gdp|gross domestic|personal income|trade in goods|international trade|current account|pce")]
    def feeds_fn(name, url, rx):
        def f():
            for x in rss(url, 30):
                if not x["time"] or now() - datetime.fromisoformat(x["time"].replace("Z", "+00:00")) > timedelta(days=7): continue
                if rx and not re.search(rx, x["title"], re.I): continue
                R.add("markets", name, x["title"], x["url"], x["time"], x["summary"][:300], ["Central bank" if "Bank" in name or "Reserve" in name or "ECB" in name else "Economic indicator"])
        return f
    def mnews_fn(name, url):
        def f():
            for x in rss(url, 80):
                if not x["time"] or now() - datetime.fromisoformat(x["time"].replace("Z", "+00:00")) > timedelta(days=2): continue
                if x["title"].rstrip().endswith("?") or not RX_MKT_NEWS.search(x["title"]): continue
                R.add("markets", name, x["title"], x["url"], x["time"], x["summary"][:300], ["News"])
        return f
    R.run_source("Yahoo Finance chart API", quotes); R.run_source("FDIC bank failures API", fdic)
    for name, url, rx in CB: R.run_source(name, feeds_fn(name, url, rx))
    for name, url in (("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"), ("Guardian Business", "https://www.theguardian.com/business/rss"),
                      ("CNBC Finance", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664"),
                      ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"), ("DW Business", "https://rss.dw.com/rdf/rss-en-bus")):
        R.run_source(name, mnews_fn(name, url))

# ------------------------------------------------------------------ scheduler (box only)
def interval_min():
    try: return max(15, int(json.load(open(os.path.join(BASE, "config.json"))).get("interval_minutes", 60)))
    except Exception: return 60
def cycle(only=None, patent_budget=700):
    c = db(); R = Run(c)
    iv = interval_min() * 60
    plan = [("research", research, iv), ("leaks", leaks, iv), ("mna", mna, min(iv, 3600)), ("markets", markets, min(iv, 1800)), ("patents", lambda r: patents(r, patent_budget), min(iv, 3600))]
    for name, fn, every in plan:
        if only and name not in only: continue
        if not only and not due(c, name, every - 60): continue
        fn(R)
    c.execute("DELETE FROM items WHERE found<?", (iso(now() - timedelta(days=KEEP_DAYS)),))
    c.execute("DELETE FROM runs WHERE ts<?", (iso(now() - timedelta(days=7)),))
    c.execute("DELETE FROM rejected WHERE ts<?", (iso(now() - timedelta(days=7)),))
    c.execute("DELETE FROM epo_seen WHERE ts<?", (iso(now() - timedelta(days=21)),))
    sset(c, "last_cycle", iso()); c.commit(); c.close()
    return R.stats
def loop():
    if WEB_ONLY: return
    while True:
        t0 = time.time()
        try: cycle()
        except Exception as ex: log("cycle error: " + repr(ex)[:300])
        time.sleep(max(120, 300 - (time.time() - t0)))   # wakes every 5 min; each stream runs on its own due time

# ------------------------------------------------------------------ catalog records for the Sources page (sources_catalog.gather)
def catalog_records():
    counts, last = {}, {}
    try:
        c = db(ro=True)
        for r in c.execute("SELECT source, COUNT(*) n, MIN(found) f, MAX(found) l FROM items GROUP BY source"): counts[r["source"]] = (r["n"], r["f"], r["l"])
        for r in c.execute("SELECT source, ok, error FROM runs WHERE rowid IN (SELECT MAX(rowid) FROM runs GROUP BY source)"): last[r["source"]] = (r["ok"], r["error"])
        c.close()
    except Exception: pass
    out = []
    for key, stream, name, url, typ, cat, rating, why, prof in SOURCES:
        n, f, l = counts.get(key, (0, None, None)); ok = last.get(key)
        st = "intel stream: " + STREAMS[stream] + (" · checked ok" if ok and ok[0] else (" · last check failed" if ok else " · not checked yet"))
        out.append(dict(key="Intel: " + key, name=name, type=typ, n=n, first=f, last=l, link=url, origin="intel streams", status=st, cats={cat: n},
                        fixed=rating, fixed_why=why, feed_profile=prof + " Informational only: never affects threat scores or ranks.",
                        stream=STREAMS[stream], grade_key="Intel: " + key, grade_seed=rating))
    return out

# ------------------------------------------------------------------ public API
def summary(qs):
    stream = (qs.get("stream") or [""])[0]; days = min(30, max(1, int((qs.get("days") or ["7"])[0] or 7)))
    try: c = db(ro=True)
    except Exception: return 200, {"items": [], "streams": {}, "note": "Intel streams are warming up."}
    try:
        cut = iso(now() - timedelta(days=days))
        q = "SELECT stream, source, title, url, published, found, summary, tags, extra, link_note FROM items WHERE found>=?" + (" AND stream=?" if stream in STREAMS else "")
        q += " ORDER BY COALESCE(published, found) DESC LIMIT 600"
        rows = c.execute(q, (cut, stream) if stream in STREAMS else (cut,)).fetchall()
        items = []
        for r in rows:
            ex = json.loads(r["extra"] or "{}")
            items.append({"stream": r["stream"], "label": STREAMS.get(r["stream"]), "source": r["source"], "title": r["title"], "url": r["url"], "time": r["published"],
                          "found": r["found"], "summary": r["summary"], "tags": json.loads(r["tags"] or "[]"), "alt": None,
                          "verified": r["link_note"] or "link answered 2xx"})
        st = {}
        for k, lab in STREAMS.items():
            n24 = c.execute("SELECT COUNT(*) FROM items WHERE stream=? AND found>=?", (k, iso(now() - timedelta(hours=24)))).fetchone()[0]
            n7 = c.execute("SELECT COUNT(*) FROM items WHERE stream=? AND found>=?", (k, cut)).fetchone()[0]
            st[k] = {"label": lab, "new_24h": n24, "items": n7, "sources": []}
        for r in c.execute("SELECT source, stream, ts, ok, n_new, error FROM runs WHERE rowid IN (SELECT MAX(rowid) FROM runs GROUP BY source)"):
            s = SOURCE_BY_KEY.get(r["source"])
            if s and r["stream"] in st: st[r["stream"]]["sources"].append({"name": s[2], "url": s[3], "checked": r["ts"], "ok": bool(r["ok"]), "new": r["n_new"],
                                                                            "error": (r["error"] or "")[:120] or None, "rating": s[6]})
        wl = {"latest": sget(c, "wl_latest"), "latest_news": sget(c, "wl_latest_news"), "checked": sget(c, "wl_checked")}
        return 200, {"updated": sget(c, "last_cycle"), "days": days, "streams": st, "items": items, "wikileaks": wl, "epo": sget(c, "epo_progress"),
                     "thresholds": {"indexes": "±3% day", "fx": "±2% day (dollar index ±1.5%)", "oil": "±5%", "natural gas": "±8%", "gold": "±3%", "copper": "±4%",
                                    "bitcoin": "±8%", "vix": "+25% or a close above 30", "us10y": "±15 bp", "mna_news": "deal ≥ $1B in the headline, or defense / critical-infrastructure"},
                     "note": "Informational streams: research papers, leak releases, patents, mergers and markets. Every link was checked before it was listed. "
                             "These items never change threat scores or ranks. Research uses OpenAlex, arXiv, PubMed and medRxiv/bioRxiv in place of Google Scholar, which offers no public feed."}
    finally: c.close()

def feed_xml(qs):
    code, d = summary(qs)
    esc = lambda s: html.escape(str(s or ""), quote=True)
    out = ['<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>blackout.network — Intel Streams</title><link>https://blackout.network/#intel</link>'
           '<description>Research, leaks, patents, M&amp;A and markets.</description>']
    for x in d.get("items", [])[:150]:
        try: pd = datetime.fromisoformat(x["time"].replace("Z", "+00:00")).strftime("%a, %d %b %Y %H:%M:%S +0000")
        except Exception: pd = ""
        out.append(f"<item><title>[{esc(x['label'])}] {esc(x['title'])}</title><link>{esc(x['url'])}</link><guid isPermaLink=\"false\">{esc(x['url'])}</guid>"
                   f"<category>{esc(x['label'])}</category><pubDate>{pd}</pubDate><description>{esc(x['summary'])}</description></item>")
    out.append("</channel></rss>")
    return 200, "".join(out).encode(), "application/rss+xml; charset=utf-8"

def handle_get(path, qs):
    n = path[len("/api/intel/"):] if path.startswith("/api/intel/") else ""
    if n in FILES:
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    if n in ("feed.xml", "rss"): return feed_xml(qs)
    if path == "/api/intel": return summary(qs)
    return 404, {"error": "not found"}

if __name__ == "__main__":
    a = sys.argv[1:] or ["once"]
    if a[0] == "loop": loop()
    elif a[0] == "once": print(json.dumps(cycle(only=set(a[1:]) or set(STREAMS), patent_budget=int(os.environ.get("BN_EPO_BUDGET", "700"))), indent=1))
    elif a[0] == "catalog": print(json.dumps(catalog_records(), indent=1)[:4000])
