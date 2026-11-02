"""Midterms 2026 tab (nav "Midterms 2026", deep link #midterms): control of the House, Senate and governorships, every Senate and
governor race plus the competitive House races, published race ratings, polling averages next to prediction-market prices, a
rating/result map, and election-night results with "as of" times. Strictly descriptive: every figure is attributed to its source.

Data (all free, keyless, public; nothing is invented or imputed):
  * Wikipedia (CC BY-SA 4.0) via the MediaWiki API: the 2026 Senate, gubernatorial and House election articles, the House election
    ratings article and each Senate/governor race article. These compile the candidates on the ballot, the published ratings of
    Cook Political Report, Inside Elections and Sabato's Crystal Ball (and others), polling aggregates (RealClearPolitics,
    Decision Desk HQ, 270toWin, Silver Bulletin ...) and, on election night, results and winners as Wikipedia editors record them.
  * Official state results feeds that are published as public JSON with no key and no bot wall: Arizona, Georgia, Virginia and
    Washington (Enhanced Voting public results API used by those states' election offices) and North Carolina (NCSBE
    er.ncsbe.gov results file). Votes, reporting units and the state's own "as of" time. We never project a winner from them.
  * Polymarket (gamma-api) and Kalshi (trade-api v2) public market prices for each race.
  * 270toWin's 2026 poll closing times page (closing times below, fetched 2026-10-31).
  AP results are licensed (not free) and are not used. Florida's results site sits behind a Cloudflare bot challenge, and Clarity/Scytl
  ENR hosts refuse automated requests (403); neither is fetched. Those states are covered by Wikipedia + a link to the official page.

Box: `python3 midterms.py loop` (run_midterms.sh) builds midterms.db (one JSON row per key; read-only for the web module); render_sync.py
pushes it to the public node like every other *.db. Cadence: base data every 3 h (every 10 min for race pages and 4 min for the summary
articles on election night, 6 PM ET Nov 3 to noon ET Nov 5); market prices every 15 min; official feeds every 2 min on election night.
`python3 midterms.py test` proves the parsers against the 2024 general election (Wikipedia + official NC/GA files).
Web (box + Render): /api/midterms, /api/midterms/live, /api/midterms/app.js|app.css|states.geojson. On election night the public node
also refreshes the official feeds itself (one short background fetch at most every 2 min, triggered by visitors) so results are fresher
than the 5-minute DB sync. Never touches scanner/scoring/push/jets."""
import os, sys, re, json, time, sqlite3, threading, gzip, html, urllib.request, urllib.parse, urllib.error
from html.parser import HTMLParser
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "midterms.db")
STATIC = os.path.join(BASE, "midterms_static")
GOVDB = os.path.join(BASE, "government.db")
UA = "blackout.network-midterms/1.0 (https://blackout.network; hello@blackout.network) read-only election page"
WIKI_API = "https://en.wikipedia.org/w/api.php"
ET = timezone(timedelta(hours=-5))          # Nov 3 2026 is after DST ends (Nov 1): Eastern Standard Time, UTC-5
ELECTION_DAY = "2026-11-03"
NIGHT_START = datetime(2026, 11, 3, 18, 0, tzinfo=ET); NIGHT_END = datetime(2026, 11, 5, 12, 0, tzinfo=ET)
PAGES = {"senate": "2026 United States Senate elections", "governor": "2026 United States gubernatorial elections",
         "house": "2026 United States House of Representatives elections", "house_ratings": "2026 United States House of Representatives election ratings"}

STATES = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO", "Connecticut": "CT",
 "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
 "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
 "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
 "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
 "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
 "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
 "District of Columbia": "DC", "Guam": "GU", "Northern Mariana Islands": "MP", "U.S. Virgin Islands": "VI", "United States Virgin Islands": "VI",
 "American Samoa": "AS", "Puerto Rico": "PR"}
ABBR_NAME = {}
for _n, _a in STATES.items(): ABBR_NAME.setdefault(_a, _n)

# Poll closing times, Eastern Time (EST on Nov 3): the LATEST closing in each state = when all of its statewide polls are closed.
# Source: 270toWin "2026 Election Poll Closing Times", https://www.270towin.com/poll-closing-times/ (fetched 2026-10-31).
POLL_CLOSE_SRC = {"label": "270toWin: 2026 Election Poll Closing Times", "url": "https://www.270towin.com/poll-closing-times/", "fetched": "2026-10-31"}
_PC = {"19:00": "GA IN KY SC VA VT", "19:30": "NC OH WV", "20:00": "AL CT DE FL IL ME MD MA MS MO NH NJ OK PA RI TN DC",
       "20:30": "AR", "21:00": "AZ CO IA KS LA MI MN NE NM NY ND SD TX WI WY", "22:00": "MT NV UT", "23:00": "CA ID OR WA",
       "24:00": "HI", "25:00": "AK"}
POLL_CLOSE = {}
for _t, _ss in _PC.items():
    _h, _m = map(int, _t.split(":"))
    for _s in _ss.split(): POLL_CLOSE[_s] = (datetime(2026, 11, 3, 0, 0, tzinfo=ET) + timedelta(hours=_h, minutes=_m)).isoformat()
# Split-time-zone states whose FIRST closing (ET) is earlier than the latest one above; checked against NCSL polling place hours
# (https://www.ncsl.org/elections-and-campaigns/polling-places, fetched 2026-11-02). Table: /workspace/seo/data/poll_close_2026-11-03.json
POLL_CLOSE_NCSL = {"label": "NCSL: Polling Place Hours", "url": "https://www.ncsl.org/elections-and-campaigns/polling-places", "fetched": "2026-11-02"}
_PC_FIRST = {"18:00": "IN KY", "19:00": "FL", "20:00": "KS MI ND SD TX", "22:00": "ID OR", "24:00": "AK"}
POLL_CLOSE_FIRST = dict(POLL_CLOSE)
for _t, _ss in _PC_FIRST.items():
    _h, _m = map(int, _t.split(":"))
    for _s in _ss.split(): POLL_CLOSE_FIRST[_s] = (datetime(2026, 11, 3, 0, 0, tzinfo=ET) + timedelta(hours=_h, minutes=_m)).isoformat()
FIRST_CLOSE = {"at": datetime(2026, 11, 3, 18, 0, tzinfo=ET).isoformat(), "where": "Eastern-time parts of Indiana and Kentucky"}
LAST_CLOSE = {"at": datetime(2026, 11, 4, 1, 0, tzinfo=ET).isoformat(), "where": "the Hawaii-Aleutian time zone of Alaska"}

OFFICIAL_LINKS = {  # each state's official election-results page (secretary of state / election board)
 "AL": "https://www.sos.alabama.gov/alabama-votes/voter/election-information", "AK": "https://www.elections.alaska.gov/election-results/",
 "AZ": "https://results.arizona.vote/", "AR": "https://www.sos.arkansas.gov/elections/research/election-results",
 "CA": "https://electionresults.sos.ca.gov/", "CO": "https://www.sos.state.co.us/pubs/elections/Results/", "CT": "https://electionhistory.ct.gov/",
 "DE": "https://elections.delaware.gov/results/", "FL": "https://results.elections.myflorida.com/", "GA": "https://results.sos.ga.gov/results/public/Georgia",
 "HI": "https://elections.hawaii.gov/election-results/", "ID": "https://voteidaho.gov/election-results/",
 "IL": "https://www.elections.il.gov/electionoperations/ElectionVoteTotals.aspx", "IN": "https://enr.indianavoters.in.gov/",
 "IA": "https://sos.iowa.gov/elections/results/", "KS": "https://sos.ks.gov/elections/election-results.html", "KY": "https://elect.ky.gov/results/",
 "LA": "https://voterportal.sos.la.gov/graphical", "ME": "https://www.maine.gov/sos/elections-voting/election-results-data", "MD": "https://elections.maryland.gov/elections/2026/index.html",
 "MA": "https://electionstats.state.ma.us/", "MI": "https://mielections.us/election/results/", "MN": "https://electionresults.sos.mn.gov/",
 "MS": "https://www.sos.ms.gov/elections-voting/election-results", "MO": "https://enr.sos.mo.gov/", "MT": "https://electionresults.mt.gov/",
 "NE": "https://electionresults.nebraska.gov/", "NV": "https://silverstateelection.nv.gov/", "NH": "https://www.sos.nh.gov/elections/election-results",
 "NJ": "https://www.nj.gov/state/elections/election-information-results.shtml", "NM": "https://electionresults.sos.nm.gov/",
 "NY": "https://nyenr.elections.ny.gov/", "NC": "https://er.ncsbe.gov/", "ND": "https://results.sos.nd.gov/", "OH": "https://liveresults.ohiosos.gov/",
 "OK": "https://results.okelections.gov/", "OR": "https://results.oregonvotes.gov/", "PA": "https://www.electionreturns.pa.gov/",
 "RI": "https://www.ri.gov/election/results/", "SC": "https://www.scvotes.gov/election-results", "SD": "https://electionresults.sd.gov/",
 "TN": "https://sos.tn.gov/elections/results", "TX": "https://results.texas-election.com/", "UT": "https://electionresults.utah.gov/",
 "VT": "https://electionarchive.vermont.gov/", "VA": "https://enr.elections.virginia.gov/", "WA": "https://results.vote.wa.gov/",
 "WV": "https://sos.wv.gov/elections/election-data/historical-election-results-and-turnout", "WI": "https://elections.wi.gov/elections/election-results",
 "WY": "https://sos.wyo.gov/Elections/ElectionResults.aspx"}

def now(): return datetime.now(timezone.utc)
def iso(d=None): return (d or now()).strftime("%Y-%m-%dT%H:%M:%SZ")
def election_night(t=None):
    t = t or now(); return NIGHT_START <= t <= NIGHT_END
def log(*a): print(time.strftime("[%Y-%m-%dT%H:%M:%SZ]", time.gmtime()), *a, flush=True)

# ------------------------------------------------------------------ tiny HTML DOM (stdlib only: the public node has no bs4)
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
class N:
    __slots__ = ("tag", "a", "kids", "up")
    def __init__(s, tag, a, up): s.tag, s.a, s.kids, s.up = tag, a, [], up
    def cls(s): return set((s.a.get("class") or "").split())
    def iter(s):
        st = [s]
        while st:
            n = st.pop(); yield n
            st.extend(k for k in reversed(n.kids) if isinstance(k, N))
    def all(s, tag=None, cls=None, skip_nested=None):
        out = []; st = list(reversed([k for k in s.kids if isinstance(k, N)]))
        while st:
            n = st.pop()
            if (tag is None or n.tag == tag) and (cls is None or cls in n.cls()): out.append(n)
            if skip_nested and n.tag == skip_nested: continue
            st.extend(k for k in reversed(n.kids) if isinstance(k, N))
        return out
    def first(s, tag=None, cls=None):
        r = s.all(tag, cls); return r[0] if r else None
    def text(s, skip=("sup", "style", "script")):
        out = []
        def w(n):
            for k in n.kids:
                if isinstance(k, str): out.append(k)
                elif k.tag in skip: continue
                elif "display:none" in (k.a.get("style") or "").replace(" ", ""): continue
                else:
                    if k.tag in ("br", "li", "p", "div", "tr", "td", "th"): out.append(" ")
                    w(k)
                    if k.tag in ("li", "p", "div", "td", "th"): out.append(" ")
        w(s)
        return re.sub(r"\s+", " ", "".join(out).replace("\xa0", " ")).strip()
    def closest(s, tag):
        n = s.up
        while n is not None and n.tag != tag: n = n.up
        return n
class _P(HTMLParser):
    def __init__(s):
        super().__init__(convert_charrefs=True); s.root = N("root", {}, None); s.cur = s.root
    def handle_starttag(s, tag, attrs):
        n = N(tag, {k: (v or "") for k, v in attrs}, s.cur); s.cur.kids.append(n)
        if tag not in VOID: s.cur = n
    def handle_startendtag(s, tag, attrs): s.cur.kids.append(N(tag, {k: (v or "") for k, v in attrs}, s.cur))
    def handle_endtag(s, tag):
        n = s.cur
        while n is not None and n.tag != tag: n = n.up
        if n is not None and n.up is not None: s.cur = n.up
    def handle_data(s, d):
        if d: s.cur.kids.append(d)
def dom(text):
    p = _P(); p.feed(text); p.close(); return p.root
def _span(c, k, cap):
    try: return max(1, min(cap, int(re.sub(r"\D", "", c.a.get(k, "1")) or 1)))
    except Exception: return 1
def grid(table):
    """Rows of a table (nested tables skipped) expanded for rowspan/colspan: list of rows, each a list of (cell, is_th)."""
    trs = [tr for tr in table.all("tr", skip_nested="table") if tr.closest("table") is table]
    out, pend = [], {}
    for tr in trs:
        row, col, ci = [], 0, 0
        cells = [c for c in tr.kids if isinstance(c, N) and c.tag in ("td", "th")]
        while ci < len(cells) or col in pend:
            if col in pend:
                c, left = pend[col]; row.append(c)
                if left <= 1: del pend[col]
                else: pend[col] = (c, left - 1)
                col += 1; continue
            c = cells[ci]; ci += 1; cs = _span(c, "colspan", 50); rs = _span(c, "rowspan", 500)
            for _ in range(cs):
                row.append((c, c.tag == "th"))
                if rs > 1: pend[col] = ((c, c.tag == "th"), rs - 1)
                col += 1
        out.append(row)
    return out
def header_split(g):
    hdr = []
    for r in g:
        if r and all(th for _, th in r): hdr.append(r)
        else: break
    return hdr, g[len(hdr):]
def colnames(hdr):
    if not hdr: return []
    w = max(len(r) for r in hdr); names = []
    for i in range(w):
        t = ""
        for r in hdr:
            if i < len(r): t = r[i][0].text() or t
        names.append(t)
    return names
def tables(root, cls="wikitable"): return [t for t in root.all("table") if cls in t.cls()]
def abs_url(u):
    if not u: return None
    if u.startswith("//"): return "https:" + u
    if u.startswith("/wiki/"): return "https://en.wikipedia.org" + u
    return u if u.startswith("http") else None

# ------------------------------------------------------------------ HTTP
_NET = {"bytes": 0, "req": 0}
def get(url, timeout=40, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip", "Accept": "application/json, text/plain, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
    _NET["bytes"] += len(b); _NET["req"] += 1
    return b if raw else json.loads(b.decode("utf-8"))
def wiki(title):
    q = urllib.parse.urlencode({"action": "parse", "page": title, "prop": "text|revid|displaytitle", "format": "json", "formatversion": 2,
                                "redirects": 1, "disableeditsection": 1, "disablelimitreport": 1})
    d = get(f"{WIKI_API}?{q}", timeout=60)
    if "error" in d: raise RuntimeError(f"wikipedia: {d['error'].get('info')}")
    p = d["parse"]; return dom(p["text"]), p["revid"], p["title"]
def wiki_revs(titles):
    """{title: {revid, ts}} for many titles, 50 per cheap query (unchanged race pages are not re-parsed)."""
    out = {}
    for i in range(0, len(titles), 50):
        q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "ids|timestamp", "titles": "|".join(titles[i:i + 50]),
                                    "format": "json", "formatversion": 2, "redirects": 1})
        d = get(f"{WIKI_API}?{q}")
        red = {r["to"]: r["from"] for r in (d.get("query", {}).get("redirects") or [])}
        norm = {r["to"]: r["from"] for r in (d.get("query", {}).get("normalized") or [])}
        for pg in d.get("query", {}).get("pages") or []:
            if pg.get("missing") or not pg.get("revisions"): continue
            t = pg["title"]; t0 = red.get(t, t); t0 = norm.get(t0, t0)
            out[t0] = out[t] = {"revid": pg["revisions"][0]["revid"], "ts": pg["revisions"][0]["timestamp"]}
        time.sleep(0.3)
    return out
def wiki_url(title, revid=None):
    u = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
    return u + (f"?oldid={revid}" if revid else "")

# ------------------------------------------------------------------ parsing helpers
PARTY = [(r"democratic|democrat\b|\bdem\b|^d$|\bdfl\b|farmer.?labor|\bd-npl\b", "D"), (r"republican|\brep\b|^r$|\bgop\b", "R"),
         (r"independent|\bind\b|^i$|nonpartisan|unaffiliated|no party|\bnpa\b", "I"), (r"libertarian|\blib\b|\blbt\b", "L"),
         (r"green|\bgrn\b|\bgre\b", "G"), (r"constitution", "C"), (r"forward", "F")]
def pcode(s):
    s = (s or "").strip().lower()
    for rx, c in PARTY:
        if re.search(rx, s): return c
    return "O" if s else None
def clean_name(s):
    s = re.sub(r"\[[^\]]*\]", "", s or ""); s = s.replace("▌", " ")
    s = re.sub(r"\((retiring|term-limited|term limited|running|incumbent|lost renomination|resigned|withdrawn|withdrew)[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"\s+(Redistricted|Moved|Switched) from .*$", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip(" ,;")
def last_name(n):
    n = re.sub(r"\([^)]*\)", "", clean_name(n)).strip()
    n = re.sub(r",?\s+\b(Jr|Sr|II|III|IV)\.?$", "", n).strip(" ,")
    parts = [p for p in re.split(r"\s+", n) if p]
    return (parts[-1] if parts else n).lower().strip('".,')
def norm_name(n): return re.sub(r"[^a-z]", "", re.sub(r"\([^)]*\)", "", clean_name(n).lower()))
RATE = {"safe": 3, "solid": 3, "likely": 2, "lean": 1, "tilt": 0.5}
def rating(s):
    s = clean_name(s); flip = "flip" in s.lower(); t = re.sub(r"\(flip\)", "", s, flags=re.I).strip()
    m = re.match(r"(safe|solid|likely|lean|tilt|very likely)\s+([DRI])\b", t, re.I)
    if m:
        k = m.group(1).lower(); k = "likely" if k == "very likely" else k; side = m.group(2).upper()
        v = RATE[k] * (-1 if side == "D" else 1 if side == "R" else 0)
        return {"t": f"{m.group(1).title()} {side}", "v": v, "flip": flip}
    if re.match(r"toss[\s-]?up", t, re.I): return {"t": "Tossup", "v": 0, "flip": False}
    return {"t": t, "v": None, "flip": flip} if t else None
MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
def rater_head(h):
    h = re.sub(r"\[[^\]]*\]", "", h).strip()
    m = re.search(rf"\b({MONTHS})[a-z]*\.?\s+(\d{{1,2}}),?\s+(\d{{4}})", h)
    name = (h[:m.start()].strip() if m else h).rstrip(".")
    date = None
    if m:
        try: date = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y").strftime("%Y-%m-%d")
        except Exception: date = None
    return name, date
RATER_FULL = {"Cook": "Cook Political Report", "IE": "Inside Elections", "Sabato": "Sabato's Crystal Ball", "DDHQ": "Decision Desk HQ",
              "Econ": "The Economist", "FPO": "FiftyPlusOne", "Fox": "Fox News", "NBC": "NBC News", "RCP": "RealClearPolitics",
              "Silver": "Silver Bulletin", "ST": "Split Ticket", "CNalysis": "CNalysis", "CNN": "CNN"}
CORE_RATERS = ("Cook", "IE", "Sabato")
def consensus(rts):
    vs = [rts[k]["v"] for k in CORE_RATERS if rts.get(k) and rts[k].get("v") is not None]
    if not vs: return None
    a = sum(vs) / len(vs); side = "D" if a < 0 else "R"; x = abs(a)
    t = "Tossup" if x < 0.5 else (f"Tilt {side}" if x < 0.75 else f"Lean {side}" if x < 1.5 else f"Likely {side}" if x < 2.5 else f"Safe {side}")
    return {"t": t, "v": round(a, 2), "n": len(vs)}
def place(label):
    """'Florida (special)' / 'Alabama 2' / 'New York at-large' -> (state abbr, district or None, special flag)."""
    s = clean_name(label).replace("\xa0", " ")
    special = bool(re.search(r"special|class 3", s, re.I))
    s2 = re.sub(r"\(.*?\)", "", s).strip()
    m = re.match(r"(.+?)\s+(\d+|at-large|at large)$", s2, re.I)
    if m and m.group(1) in STATES: return STATES[m.group(1)], ("AL" if "large" in m.group(2).lower() else int(m.group(2))), special
    for n in sorted(STATES, key=len, reverse=True):
        if s2 == n or s2.startswith(n + " ") or s2.startswith(n + "["): return STATES[n], None, special
    return None, None, special
def _wiki_a(li):
    for x in li.all("a"):
        h = x.a.get("href") or ""
        if h.startswith("/wiki/") and "Party" not in h and not h.startswith("/wiki/File:") and not h.startswith("/wiki/Help:"): return x
    return None
def cand_list(cell):
    """Candidates from a 'Candidates' cell: [{name, party, code, winner, pct, wiki}]"""
    out = []
    for li in (cell.all("li") or [cell]):
        txt = li.text()
        if not txt or txt.strip("▌ ") == "": continue
        win = any((im.a.get("alt") or "").lower() in ("green tick", "green check", "check", "y", "yes") for im in li.all("img")) or \
              any(k.text(skip=()) == "Y" and "display:none" in (k.a.get("style") or "").replace(" ", "") for k in li.all("span"))
        t = re.sub(r"^[▌\s]+", "", txt).replace("▌", " ").strip()
        m = re.match(r"^(.*?)\s*\(\s*([^()]+?)\s*\)\s*(\d+(?:\.\d+)?)?\s*%?\s*(.*)$", t)
        if m: name, party, pct = m.group(1), m.group(2), m.group(3)
        else: name, party, pct = t, "", None
        name = clean_name(re.sub(r"^Y\s+", "", name))
        if not name or name.lower() in ("tbd", "none", "tba"): continue
        a = _wiki_a(li)
        wk = abs_url(a.a.get("href")) if a and last_name(a.text()) == last_name(name) else None
        out.append({"name": name, "party": party, "code": pcode(party), "winner": bool(win), "pct": float(pct) if pct else None, "wiki": wk})
    return out
def cell_link(c):
    a = _wiki_a(c); return abs_url(a.a.get("href")) if a else None

# ------------------------------------------------------------------ article parsers
def parse_balance(root):
    """Infobox party columns: {party: {label: value}} (Current seats, Seats needed, Seats up, Seats before, Seats won, Seat change ...)."""
    ib = next((t for t in root.all("table") if "infobox" in t.cls()), None)
    if not ib: return {}
    out, parties = {}, []
    for tr in ib.all("tr"):
        cells = [c for c in tr.kids if isinstance(c, N) and c.tag in ("th", "td")]
        if len(cells) < 2: continue
        lab = cells[0].text().replace("\xa0", " ").strip(); vals = [c.text() for c in cells[1:]]
        if lab == "Party":
            parties = vals
            for p in parties:
                if p: out.setdefault(p, {})
            continue
        if parties and re.match(r"(Current seats|Seats needed|Seats up|Seats before|Seats won|Seat change|Last election|Popular vote|Percentage|Swing|Seats after)", lab):
            for p, v in zip(parties, vals):
                if p: out[p][lab] = re.sub(r"\[[^\]]*\]", "", v).strip()
    return out
def parse_ratings(t):
    g = grid(t); hdr, rows = header_split(g); names = colnames(hdr)
    try: first_r = next(i for i, n in enumerate(names) if re.match(r"Last", n))
    except StopIteration: return {}, []
    raters = [(i,) + rater_head(names[i]) for i in range(first_r + 1, len(names))]
    raters = [x for x in raters if x[1] and x[1].lower() not in ("ratings", "rating")]
    out = {}
    for r in rows:
        if len(r) <= first_r + 1: continue
        lab = r[0][0].text(); st, dist, special = place(lab)
        if not st: continue
        rts = {}
        for i, nm, dt in raters:
            if i >= len(r): continue
            v = rating(r[i][0].text())
            if v: rts[nm] = dict(v, date=dt)
        out[(st, dist, special)] = {"label": clean_name(lab), "pvi": r[1][0].text() if "PVI" in names[1].upper() else None,
                                    "incumbent_note": r[2][0].text() if len(r) > 2 else "", "last": r[first_r][0].text(), "ratings": rts}
    return out, [{"key": nm, "name": RATER_FULL.get(nm, nm), "date": dt} for _, nm, dt in raters]
def parse_summary(t, office):
    """Race-summary table (Senate / governor / House state tables) -> list of race dicts."""
    g = grid(t); hdr, rows = header_split(g); names = colnames(hdr); low = [n.lower() for n in names]
    def ci(*keys):
        for k in keys:
            for i, n in enumerate(low):
                if n.startswith(k): return i
        return None
    c_name = ci("senator", "governor", "member", "representative"); c_party = ci("party"); c_status = ci("status", "results", "this race")
    c_cand = ci("candidates"); c_pvi = ci("pvi", "2026 pvi", "cpvi"); c_last = ci("last race", "last election")
    if c_cand is None: return []
    out, seen = [], {}
    for r in rows:
        if len(r) <= c_cand: continue
        lab = r[0][0].text(); st, dist, special = place(lab)
        if not st: continue
        key = (st, dist, special)
        inc_name = clean_name(r[c_name][0].text()) if c_name is not None else ""
        inc_party = r[c_party][0].text() if c_party is not None else ""
        status = re.sub(r"\[[^\]]*\]", "", r[c_status][0].text()).strip() if c_status is not None else ""
        if inc_party == inc_name: inc_party = ""
        inc = None if (not inc_name or re.match(r"(none|vacant)", inc_name, re.I)) else \
            {"name": inc_name, "party": inc_party, "code": pcode(inc_party), "wiki": cell_link(r[c_name][0]), "status": status}
        if key in seen:      # a second incumbent row inside a rowspan (two members running for one seat)
            if inc and inc["name"] not in [x["name"] for x in seen[key]["incumbents"]]: seen[key]["incumbents"].append(inc)
            continue
        rr = {"key": key, "office": office, "state": st, "district": dist, "special": special, "label": clean_name(lab),
              "article": cell_link(r[0][0]), "pvi": r[c_pvi][0].text() if c_pvi is not None else None,
              "last": r[c_last][0].text() if c_last is not None else None, "status": status,
              "incumbents": [inc] if inc else [], "candidates": cand_list(r[c_cand][0])}
        seen[key] = rr; out.append(rr)
    return out
def _skip_col(n): return re.match(r"(other|undecided|margin|lead|none|someone else|wouldn)", n.strip(), re.I)
def parse_aggregates(t):
    g = grid(t); hdr, rows = header_split(g); names = colnames(hdr)
    iu = next((i for i, n in enumerate(names) if n.lower().startswith("dates updated")), 2)
    cand_cols = [(i, re.sub(r"\[[^\]]*\]", "", names[i]).strip()) for i in range(iu + 1, len(names)) if not _skip_col(names[i])]
    i_m = next((i for i, n in enumerate(names) if n.lower().startswith("margin")), None)
    i_o = next((i for i, n in enumerate(names) if re.match(r"other|undecided", n, re.I)), None)
    out = []
    for r in rows:
        if len(r) < 3: continue
        r = r + [(N("td", {}, None), False)] * (len(names) - len(r))
        src = re.sub(r"\[[^\]]*\]", "", r[0][0].text()).strip()
        a = next((x for x in r[0][0].all("a") if (x.a.get("href") or "").startswith("http")), None)
        vals = {}
        for i, nm in cand_cols:
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", r[i][0].text())
            if m: vals[nm] = float(m.group(1))
        if not vals or not src: continue
        out.append({"source": src, "url": a.a.get("href") if a else None, "administered": r[1][0].text(), "updated": r[iu][0].text() if iu < len(r) else None,
                    "values": vals, "other": r[i_o][0].text() if i_o is not None else None, "margin": r[i_m][0].text() if i_m is not None else None})
    return [nm for _, nm in cand_cols], out
def parse_polls(t, limit=5):
    g = grid(t); hdr, rows = header_split(g); names = colnames(hdr)
    im = next((i for i, n in enumerate(names) if n.lower().startswith("margin of error")), None)
    if im is None: return [], []
    cand_cols = [(i, re.sub(r"\[[^\]]*\]", "", names[i]).strip()) for i in range(im + 1, len(names)) if not _skip_col(names[i])]
    out = []
    for r in rows:
        if len(out) >= limit: break
        if len(r) < 3: continue
        r = r + [(N("td", {}, None), False)] * (len(names) - len(r))
        src = re.sub(r"\[[^\]]*\]", "", r[0][0].text()).strip()
        a = next((x for x in r[0][0].all("a") if (x.a.get("href") or "").startswith("http")), None)
        vals = {}
        for i, nm in cand_cols:
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", r[i][0].text())
            if m: vals[nm] = float(m.group(1))
        if not vals or not src: continue
        out.append({"source": src, "url": a.a.get("href") if a else None, "dates": r[1][0].text(), "sample": r[2][0].text() if len(r) > 2 else None,
                    "moe": r[im][0].text(), "values": vals})
    return [nm for _, nm in cand_cols], out
def section_tables(root):
    """[(h2 text, h3 text, table)] in document order."""
    out = []; h2 = h3 = ""
    for n in root.iter():
        if n.tag == "h2": h2 = n.text(); h3 = ""
        elif n.tag == "h3": h3 = n.text()
        elif n.tag == "table": out.append((h2, h3, n))
    return out
def match_cols(cols, cands):
    ln = {last_name(c) for c in cols}
    return sum(1 for c in cands if last_name(c["name"]) in ln)
def parse_results_table(t):
    g = grid(t); hdr, rows = header_split(g); res, status, total = [], None, None
    for r in rows:
        uniq = []
        for c, _ in r:
            if not uniq or uniq[-1] is not c: uniq.append(c)
        ut = [c.text() for c in uniq]; j = " ".join(ut).strip()
        if re.search(r"\b(hold|gain|pickup)\b", j, re.I) and len(uniq) <= 3: status = clean_name(j); continue
        if j.lower().startswith("total votes"): total = ut[1] if len(ut) > 1 else None; continue
        fn = next((c for c in uniq if "fn" in c.cls()), None); org = next((c for c in uniq if "org" in c.cls()), None)
        if not fn: continue
        nums = [x for x in ut if re.fullmatch(r"[\d,]+", x.strip())]; pcts = [x for x in ut if re.fullmatch(r"\d+(\.\d+)?%", x.strip())]
        res.append({"name": clean_name(re.sub(r"\(incumbent\)", "", fn.text())), "incumbent": "(incumbent)" in fn.text(), "party": org.text() if org else "",
                    "code": pcode(org.text() if org else ""), "votes": int(nums[0].replace(",", "")) if nums else None,
                    "pct": float(pcts[0].rstrip("%")) if pcts else None, "bold": fn.first("b") is not None})
    winner = None
    if status:
        b = [x for x in res if x["bold"]]
        if len(b) == 1: winner = b[0]["name"]
    return {"candidates": res, "status": status, "total": total, "winner": winner}
def parse_infobox_photos(root):
    ib = next((t for t in root.all("table") if "infobox" in t.cls()), None)
    if not ib: return {}
    trs = ib.all("tr"); out = {}
    for i, tr in enumerate(trs):
        cells = [c for c in tr.kids if isinstance(c, N) and c.tag in ("td", "th")]
        if len(cells) < 2 or not any(c.first("img") is not None for c in cells): continue
        for tr2 in trs[i + 1:i + 3]:
            c2 = [c for c in tr2.kids if isinstance(c, N) and c.tag in ("td", "th")]
            if c2 and c2[0].text() in ("Nominee", "Candidate"):
                for c, nc in list(zip(cells, c2))[1:]:     # same column index in the photo row and the Nominee row
                    im = c.first("img"); nm = clean_name(nc.text())
                    if im is not None and nm:
                        src = abs_url(im.a.get("src")); a = im.closest("a")
                        if src and not re.search(r"Flag_of|Seal_of|Blank|Silhouette|placeholder", src, re.I):
                            out[last_name(nm)] = {"src": src, "name": nm, "file": abs_url(a.a.get("href")) if a else None}
                break
    return out
def race_page(title, race):
    """Per-race article: polling aggregates + recent polls matching the general-election candidates, results table, photos."""
    root, revid, t = wiki(title)
    main = ([c for c in race["candidates"] if c.get("code") in ("D", "R")] or race["candidates"][:2])[:4]
    need = min(2, len(main))
    aggs = polls = None
    secs = section_tables(root)
    for h2, h3, tb in secs:
        if "wikitable" not in tb.cls() or "primary" in (h2 + " " + h3).lower(): continue
        g0 = grid(tb)
        if not g0 or not g0[0]: continue
        h0 = g0[0][0][0].text().lower()
        if h0.startswith("source of poll aggregation") and aggs is None:
            cols, rows = parse_aggregates(tb)
            if rows and need and match_cols(cols, main) >= need: aggs = {"columns": cols, "rows": rows, "section": h3 or h2}
        elif h0.startswith("poll source") and polls is None:
            cols, rows = parse_polls(tb)
            if rows and need and match_cols(cols, main) >= need: polls = {"columns": cols, "rows": rows, "section": h3 or h2}
    res = None
    for h2, h3, tb in secs:
        if "plainrowheaders" in tb.cls() and "wikitable" in tb.cls():
            cap = tb.first("caption"); ct = ((cap.text() if cap else "") + " " + h2 + " " + h3).lower()
            if "primary" in ct or "runoff" in ct or "convention" in ct: continue
            res = parse_results_table(tb)       # the last non-primary results table is the general election
    return {"title": t, "revid": revid, "url": wiki_url(t), "aggregates": aggs, "polls": polls, "results": res, "photos": parse_infobox_photos(root)}

# ------------------------------------------------------------------ Government-tab links (the box has government.db)
def gov_links(races):
    if not os.path.exists(GOVDB): return
    c = sqlite3.connect(f"file:{GOVDB}?mode=ro", uri=True, timeout=10)
    try:
        sen, hou = {}, {}
        for nid, name, ph, par, dist in c.execute("SELECT id, name, photo_status, parent, district FROM nodes WHERE id LIKE 'bio:%'"):
            if (par or "").startswith("leg:senate:"): sen.setdefault(par[11:], []).append((nid, name, ph))
            elif (par or "").startswith("leg:house:"): hou.setdefault(par[10:], []).append((nid, name, ph, str(dist or "")))
        govs = {r[0][4:]: r for r in c.execute("SELECT id, name, photo_status FROM nodes WHERE id LIKE 'gov:%'")}
        for r in races:
            for inc in r.get("incumbents") or []:
                row = None; ln = last_name(inc["name"])
                if r["office"] == "governor":
                    g = govs.get(r["state"])
                    if g and last_name(g[1]) == ln: row = g
                elif r["office"] == "senate":
                    row = next((x for x in sen.get(r["state"], []) if last_name(x[1]) == ln), None)
                else:
                    cand = [x for x in hou.get(r["state"], []) if last_name(x[1]) == ln]
                    d = "0" if r["district"] == "AL" else str(r["district"])
                    row = next((x for x in cand if x[3] in (d, "AL", "At-Large", "at-large") or (r["district"] == "AL" and x[3] in ("", "0", "1"))), None) or (cand[0] if len(cand) == 1 else None)
                if row: inc["gov_id"] = row[0]; inc["photo"] = f"/api/government/img?id={urllib.parse.quote(row[0])}" if row[2] == "ok" else None
    finally: c.close()

# ------------------------------------------------------------------ build (box)
def _rid(office, st, dist, special):
    return f"{office[:3]}-{st}" + (f"-{dist}" if dist is not None else "")
def build_base(prev=None, race_pages=True, only_changed=True):
    prev = prev or {}; src = {}; roots = {}
    for k, title in PAGES.items():
        root, revid, t = wiki(title); roots[k] = root
        src[k] = {"title": t, "revid": revid, "url": wiki_url(t), "permalink": wiki_url(t, revid), "fetched": iso()}
        time.sleep(0.5)
    out = {"built": iso(), "sources": src,
           "balance": {"senate": parse_balance(roots["senate"]), "house": parse_balance(roots["house"]), "governor": parse_balance(roots["governor"])}}
    def hdr0(tb):
        hdr, _ = header_split(grid(tb)); return hdr, " ".join(colnames(hdr)).lower(), " ".join(c[0].text().lower() for c in (hdr[0] if hdr else []))
    sen_r, sen_meta, races = {}, [], []
    for tb in tables(roots["senate"]):
        hdr, j, h0 = hdr0(tb)
        if "ratings" in h0 and not sen_r: sen_r, sen_meta = parse_ratings(tb)
        elif "candidates" in j and "senator" in j: races += parse_summary(tb, "senate")
        elif "source of poll aggregation" in j and "generic" not in out:
            cols, rows = parse_aggregates(tb); out["generic"] = {"columns": cols, "rows": rows, "source": src["senate"]}
    gov_r, gov_meta = {}, []
    for tb in tables(roots["governor"]):
        hdr, j, h0 = hdr0(tb)
        if "ratings" in h0 and not gov_r: gov_r, gov_meta = parse_ratings(tb)
        elif "candidates" in j and "governor" in j: races += parse_summary(tb, "governor")
    hr, h_meta = {}, []
    for tb in tables(roots["house_ratings"]):
        hdr, j, h0 = hdr0(tb)
        if "ratings" in h0: hr, h_meta = parse_ratings(tb); break
    house = []
    for tb in tables(roots["house"]):
        hdr, j, h0 = hdr0(tb)
        if "candidates" in j and "member" in j: house += parse_summary(tb, "house")
    hd = {}
    for r in house:      # later tables (the regular general-election tables) win over the earlier special-election table
        if r["state"] in ABBR_NAME and r["state"] not in ("GU", "MP", "VI", "AS", "PR", "DC"): hd[(r["state"], r["district"])] = r
    house = list(hd.values())
    races = [r for r in races if not (r["office"] == "governor" and r["state"] == "DC")]   # DC elects a mayor, not a governor
    def att(r, table):
        k = (r["state"], r["district"], r["special"])
        x = table.get(k) or table.get((r["state"], r["district"], not r["special"]))
        r["ratings"] = x["ratings"] if x else {}; r["consensus"] = consensus(r["ratings"]) if x else None
        if x and not r.get("pvi"): r["pvi"] = x.get("pvi")
    for r in races: att(r, sen_r if r["office"] == "senate" else gov_r)
    for r in house: att(r, hr)
    for r in races + house:
        r["id"] = _rid(r["office"], r["state"], r["district"], r["special"]); r.pop("key", None)
        r["poll_close"] = POLL_CLOSE.get(r["state"]); r["state_name"] = ABBR_NAME.get(r["state"])
        for c in r["candidates"]:
            c["incumbent"] = any((i.get("wiki") and c.get("wiki") == i.get("wiki")) or norm_name(c["name"]) == norm_name(i["name"]) for i in r["incumbents"])
    out["ratings_meta"] = {"senate": sen_meta, "governor": gov_meta, "house": h_meta}
    out["ratings_sources"] = {"senate": src["senate"], "governor": src["governor"], "house": src["house_ratings"]}
    prev_pages = {x["id"]: x.get("page") for x in (prev.get("races") or []) if x.get("page")}
    titles = []
    for r in races:
        if r.get("article"): r["_title"] = urllib.parse.unquote(r["article"].split("/wiki/", 1)[1]).replace("_", " "); titles.append(r["_title"])
    revs = {}
    if race_pages:
        try: revs = wiki_revs(titles)
        except Exception as e: log("revs failed", e)
    for r in races:
        t = r.pop("_title", None); pp = prev_pages.get(r["id"])
        if not t: continue
        if not race_pages or (only_changed and pp and revs.get(t) and pp.get("revid") == revs[t]["revid"]): r["page"] = pp; continue
        try: r["page"] = race_page(t, r)
        except Exception as e: log("race page failed", t, repr(e)); r["page"] = pp
        time.sleep(0.4)
    for r in races:
        ph = (r.get("page") or {}).get("photos") or {}
        for c in r["candidates"]:
            p = ph.get(last_name(c["name"]))
            if p: c["photo"] = p["src"]; c["photo_file"] = p.get("file")
    gov_links(races + house)
    for r in races + house:
        for c in r["candidates"]:
            if not c.get("incumbent"): continue
            i = next((i for i in r["incumbents"] if norm_name(i["name"]) == norm_name(c["name"]) or (i.get("wiki") and i.get("wiki") == c.get("wiki"))), None) \
                or (r["incumbents"][0] if len(r["incumbents"]) == 1 else None)
            if i and i.get("gov_id"): c["gov_id"] = i["gov_id"]; c["gov_photo"] = i.get("photo")
    out["races"] = races; out["house"] = house
    out["counts"] = {"senate": sum(1 for r in races if r["office"] == "senate"), "governor": sum(1 for r in races if r["office"] == "governor"),
                     "house": len(house), "house_rated": sum(1 for r in house if r.get("ratings")),
                     "candidates": sum(len(r["candidates"]) for r in races + house)}
    return out

# ------------------------------------------------------------------ prediction markets (public prices; not forecasts of vote share)
PM = "https://gamma-api.polymarket.com"; KS = "https://api.elections.kalshi.com/trade-api/v2"
SLUG_STATE = {n.lower().replace(" ", "-").replace(".", ""): a for n, a in STATES.items()}
def pm_event(e):
    oc = []
    for m in e.get("markets") or []:
        if m.get("closed") or not m.get("outcomePrices"): continue
        try: pr = [float(x) for x in json.loads(m["outcomePrices"])]; nm = json.loads(m.get("outcomes") or "[]")
        except Exception: continue
        if [x.lower() for x in nm] == ["yes", "no"]:
            name = (m.get("groupItemTitle") or m.get("question") or "").strip()
            if not name or re.fullmatch(r"((Person|Candidate|Party)\s*)?[A-Z]|Other", name): continue
            oc.append({"name": name, "p": pr[0]})
        else:
            for n, p in zip(nm, pr): oc.append({"name": n, "p": p})
    oc.sort(key=lambda x: -x["p"])
    return {"src": "Polymarket", "title": e.get("title"), "url": f"https://polymarket.com/event/{e.get('slug')}", "outcomes": oc[:5],
            "volume": round(float(e.get("volume") or 0)), "vol_unit": "USD", "updated": e.get("updatedAt")}
def ks_event(e):
    oc = []
    for m in e.get("markets") or []:
        if m.get("status") not in ("active", "open"): continue
        last = float(m.get("last_price_dollars") or 0); bid = float(m.get("yes_bid_dollars") or 0); ask = float(m.get("yes_ask_dollars") or 0)
        if last > 0: p, basis = last, "last trade"
        elif ask > 0: p, basis = round((bid + ask) / 2, 4), "bid/ask midpoint"
        else: continue
        oc.append({"name": (m.get("yes_sub_title") or m.get("title") or "").strip(), "p": p, "basis": basis})
    oc.sort(key=lambda x: -x["p"])
    return {"src": "Kalshi", "title": e.get("title"), "url": f"https://kalshi.com/markets/{(e.get('series_ticker') or '').lower()}", "outcomes": oc[:5],
            "ticker": e.get("event_ticker")}
def build_odds(races):
    odds, errs = {}, []
    pm = []
    for off in range(0, 2000, 100):
        try: d = get(f"{PM}/events?" + urllib.parse.urlencode({"tag_slug": "midterms", "closed": "false", "limit": 100, "offset": off}))
        except Exception as e: errs.append(f"polymarket offset {off}: {e}"); break
        pm += d
        if len(d) < 100: break
        time.sleep(0.3)
    for e in pm:
        s = e.get("slug") or ""; rid = None
        m = re.match(r"^([a-z-]+?)-senate-election-winner(-\d+)?$", s)
        if m and m.group(1) in SLUG_STATE: rid = f"sen-{SLUG_STATE[m.group(1)]}"
        m = re.match(r"^([a-z-]+?)-governor-(winner-2026|election-winner|election-2026)$", s)
        if m and m.group(1) in SLUG_STATE: rid = f"gov-{SLUG_STATE[m.group(1)]}"
        m = re.match(r"^([a-z]{2})-(\d{2}|al)-house-election-winner$", s) or re.match(r"^which-party-will-win-the-house-race-for-the-([a-z]{2})-(\d{2}|al)-seat$", s)
        if m: rid = f"hou-{m.group(1).upper()}-" + ("AL" if m.group(2) == "al" else str(int(m.group(2))))
        if s == "which-party-will-win-the-house-in-2026": rid = "control-house"
        if s == "which-party-will-win-the-senate-in-2026": rid = "control-senate"
        if rid:
            ev = pm_event(e)
            if ev["outcomes"] and not any(x["src"] == "Polymarket" for x in odds.get(rid, [])): odds.setdefault(rid, []).append(ev)
    def ks_series(series, rid):
        try: d = get(f"{KS}/events?" + urllib.parse.urlencode({"series_ticker": series, "with_nested_markets": "true", "status": "open"}), timeout=30)
        except Exception as e: errs.append(f"kalshi {series}: {e}"); return
        for e in d.get("events") or []:
            if not re.search(r"-(26|2026)$", e.get("event_ticker") or ""): continue
            ev = ks_event(e)
            if ev["outcomes"]: odds.setdefault(rid, []).append(ev); break
    for s in sorted({r["state"] for r in races if r["office"] == "senate"}): ks_series(f"SENATE{s}", f"sen-{s}"); time.sleep(0.15)
    for s in sorted({r["state"] for r in races if r["office"] == "governor"}): ks_series(f"GOVPARTY{s}", f"gov-{s}"); time.sleep(0.15)
    ks_series("CONTROLH", "control-house"); ks_series("CONTROLS", "control-senate")
    cur = ""
    for _ in range(15):
        q = {"series_ticker": "KXHOUSERACE", "with_nested_markets": "true", "status": "open", "limit": 200}
        if cur: q["cursor"] = cur
        try: d = get(f"{KS}/events?" + urllib.parse.urlencode(q), timeout=40)
        except Exception as e: errs.append(f"kalshi house: {e}"); break
        for e in d.get("events") or []:
            m = re.match(r"KXHOUSERACE-([A-Z]{2})(\d{2}|AL)-26$", e.get("event_ticker") or "")
            if m:
                ev = ks_event(e)
                if ev["outcomes"]: odds.setdefault(f"hou-{m.group(1)}-" + ("AL" if m.group(2) == "AL" else str(int(m.group(2)))), []).append(ev)
        cur = d.get("cursor")
        if not cur or not d.get("events"): break
        time.sleep(0.25)
    return {"fetched": iso(), "odds": odds, "n": len(odds), "errors": errs[:20],
            "note": "Market prices are what traders pay for a contract that pays $1 if the outcome happens. They are not polls and not official results."}

# ------------------------------------------------------------------ official results feeds (box + public node)
EV = "https://app.enhancedvoting.com/results/public/api"
EV_STATES = {"AZ": ("Arizona", "https://app.enhancedvoting.com/results/public/Arizona"), "GA": ("Georgia", "https://results.sos.ga.gov/results/public/Georgia"),
             "VA": ("Virginia", "https://app.enhancedvoting.com/results/public/Virginia"), "WA": ("Washington", "https://app.enhancedvoting.com/results/public/Washington")}
EV_LABEL = {"AZ": "Arizona Secretary of State", "GA": "Georgia Secretary of State", "VA": "Virginia Department of Elections", "WA": "Washington Secretary of State"}
def contest_kind(name):
    l = re.sub(r"\s+", " ", (name or "").strip().lower())
    if re.match(r"^(nc|n\.c\.|state of \w+) (house|senate)\b", l): return None
    if not l or l.startswith("lieutenant") or l.startswith("state ") or re.search(r"house of delegates|legislat|precinct|county|school|judge|justice|court|city", l): return None
    if re.search(r"(united states senat|u\.?\s?s\.? senat|\bus senat)", l): return ("senate", None)
    if re.match(r"^(nc |state of [a-z]+ )?governor\b", l): return ("governor", None)
    if re.search(r"(house of representatives|representative in congress|u\.s\. representative|congressional district)", l) and \
       (re.search(r"congress|\bu\.?s\.?\b|united states", l) or l.startswith("member, house of representatives")):
        m = re.search(r"(\d+)", l); return ("house", int(m.group(1)) if m else "AL")
    return None
_SUFFIX = re.compile(r"\s*\((REP|DEM|GRN|LBT|LIB|IND|NOL|PND|Rep|Dem|Lib|Ind|Grn)\)")
def ev_feed(st, election_date=ELECTION_DAY):
    name, page = EV_STATES[st]
    j = get(f"{EV}/jurisdictions/{urllib.parse.quote(name)}", timeout=30)
    el = next((e for e in j.get("elections") or [] if (e.get("electionDate") or "").startswith(election_date)), None)
    if not el: return {"state": st, "ok": True, "published": False, "note": f"The state has not listed its {election_date} general election on this feed yet; it is checked again automatically.",
                       "source": EV_LABEL[st], "url": page, "checked": iso()}
    pid = el["publicElectionId"]
    d = get(f"{EV}/elections/{urllib.parse.quote(name)}/{urllib.parse.quote(pid)}/data", timeout=90)
    e = d.get("election") or {}; contests = []
    for b in d.get("ballotItems") or []:
        nm = ((b.get("name") or [{}])[0] or {}).get("text") or ""; k = contest_kind(nm)
        if not k: continue
        rs = b.get("reportingStatus") or {}; opts = []
        for o in ((b.get("summaryResults") or {}).get("ballotOptions") or []):
            on = ((o.get("name") or [{}])[0] or {}).get("text") or ""
            if re.search(r"write-?in", on, re.I) and not o.get("voteCount"): continue
            pa = (o.get("party") or {}).get("abbreviation") or (_SUFFIX.search(on).group(1) if _SUFFIX.search(on) else "")
            opts.append({"name": _SUFFIX.sub("", on).strip(), "party": pa, "code": pcode(pa), "votes": int(o.get("voteCount") or 0), "winner_by_state": bool(o.get("isWinner"))})
        tot = sum(o["votes"] for o in opts)
        for o in opts: o["pct"] = round(100 * o["votes"] / tot, 2) if tot else None
        opts.sort(key=lambda o: -o["votes"])
        contests.append({"contest": nm, "kind": k[0], "district": k[1], "reporting": rs.get("reportingUnits"), "total_units": rs.get("totalUnits"),
                         "unit": "counties", "as_of": rs.get("asOf") or e.get("asOf"), "votes": tot, "options": opts})
    return {"state": st, "ok": True, "published": True, "election": ((e.get("name") or [{}])[0] or {}).get("text"), "election_id": pid,
            "official": bool(e.get("isOfficialResults")), "as_of": e.get("asOf"), "last_updated": e.get("lastUpdated"), "source": EV_LABEL[st],
            "url": f"{page}/elections/{pid}", "contests": contests, "checked": iso()}
def nc_feed(ymd="20261103"):
    url = f"https://er.ncsbe.gov/enr/{ymd}/data/results_0.txt"
    d = get(url, timeout=90); by = {}
    for x in d:
        k = contest_kind(x.get("cnm") or "")
        if not k: continue
        c = by.setdefault(x["cnm"], {"contest": x["cnm"], "kind": k[0], "district": k[1], "reporting": int(x.get("prt") or 0), "total_units": int(x.get("ptl") or 0),
                                     "unit": "precincts", "options": []})
        c["options"].append({"name": x.get("bnm"), "party": x.get("pty"), "code": pcode(x.get("pty")), "votes": int(x.get("vct") or 0)})
    contests = []
    for c in by.values():
        tot = sum(o["votes"] for o in c["options"]); c["votes"] = tot
        for o in c["options"]: o["pct"] = round(100 * o["votes"] / tot, 2) if tot else None
        c["options"].sort(key=lambda o: -o["votes"]); contests.append(c)
    asof = None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA}), timeout=20) as r: lm = r.headers.get("Last-Modified")
        if lm: asof = datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception: pass
    for c in contests: c["as_of"] = asof
    return {"state": "NC", "ok": True, "published": True, "election": f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]} General Election", "as_of": asof,
            "as_of_basis": "Last-Modified time of the state's results file", "source": "North Carolina State Board of Elections",
            "url": f"https://er.ncsbe.gov/?election_dt={ymd[4:6]}/{ymd[6:]}/{ymd[:4]}", "contests": contests, "checked": iso()}
def build_official():
    out = {}
    for st in EV_STATES:
        try: out[st] = ev_feed(st)
        except Exception as e: out[st] = {"state": st, "ok": False, "error": str(e)[:200], "source": EV_LABEL[st], "url": EV_STATES[st][1], "checked": iso()}
        time.sleep(0.3)
    try: out["NC"] = nc_feed()
    except Exception as e: out["NC"] = {"state": "NC", "ok": False, "error": str(e)[:200], "source": "North Carolina State Board of Elections", "url": "https://er.ncsbe.gov/", "checked": iso()}
    return {"fetched": iso(), "feeds": out}

# ------------------------------------------------------------------ DB (box writes; web reads with mode=ro)
def wdb():
    c = sqlite3.connect(DB, timeout=30); c.execute("CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT, at TEXT)"); return c
def put(k, v):
    c = wdb()
    try: c.execute("INSERT OR REPLACE INTO kv VALUES(?,?,?)", (k, json.dumps(v, ensure_ascii=False, separators=(",", ":")), iso())); c.commit()
    finally: c.close()
def rget(k):
    if not os.path.exists(DB): return None, None
    try:
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
        try:
            r = c.execute("SELECT v, at FROM kv WHERE k=?", (k,)).fetchone()
            return (json.loads(r[0]), r[1]) if r else (None, None)
        finally: c.close()
    except sqlite3.Error: return None, None
def store_base(d):
    """One row per race, so a single bad row can never take the whole tab down."""
    races = d.pop("races"); house = d.pop("house")
    c = wdb()
    try:
        c.execute("INSERT OR REPLACE INTO kv VALUES(?,?,?)", ("base", json.dumps(d, ensure_ascii=False, separators=(",", ":")), iso()))
        c.execute("INSERT OR REPLACE INTO kv VALUES(?,?,?)", ("races_index", json.dumps([r["id"] for r in races]), iso()))
        c.execute("INSERT OR REPLACE INTO kv VALUES(?,?,?)", ("house_index", json.dumps([r["id"] for r in house]), iso()))
        for r in races + house: c.execute("INSERT OR REPLACE INTO kv VALUES(?,?,?)", ("race:" + r["id"], json.dumps(r, ensure_ascii=False, separators=(",", ":")), iso()))
        c.commit()
    finally: c.close()
    d["races"] = races; d["house"] = house
def load_base():
    b, _ = rget("base")
    if not b: return None
    idx, _ = rget("races_index"); hidx, _ = rget("house_index")
    try:
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
        try: rows = {k[5:]: json.loads(v) for k, v in c.execute("SELECT k, v FROM kv WHERE k LIKE 'race:%'")}
        finally: c.close()
    except sqlite3.Error: rows = {}
    b["races"] = [rows[i] for i in (idx or []) if i in rows]; b["house"] = [rows[i] for i in (hidx or []) if i in rows]
    return b

# ------------------------------------------------------------------ pipeline test: the same code against the 2024 general election
def pipeline_test():
    rep = {"ran": iso(), "checks": []}
    def ck(name, fn):
        t0 = time.time()
        try: ok, detail = fn()
        except Exception as e: ok, detail = False, f"error: {e!r}"[:300]
        rep["checks"].append({"name": name, "ok": bool(ok), "detail": detail, "ms": int(1000 * (time.time() - t0))}); log("TEST", name, ok, detail)
    def summ(title, office, word):
        root, rev, t = wiki(title); rs = []
        for tb in tables(root):
            nm = " ".join(colnames(header_split(grid(tb))[0])).lower()
            if "candidates" in nm and word in nm: rs += parse_summary(tb, office)
        return rs, rev
    def t_sen():
        rs, rev = summ("2024 United States Senate elections", "senate", "senator")
        w = [r for r in rs if any(c["winner"] for c in r["candidates"])]
        paw = next((c["name"] for r in rs if r["state"] == "PA" for c in r["candidates"] if c["winner"]), None)
        return len(w) >= 34 and paw == "Dave McCormick", f"{len(rs)} rows parsed, {len(w)} with a winner marked; Pennsylvania winner = {paw} (revision {rev})"
    def t_page():
        p = race_page("2024 United States Senate election in Pennsylvania", {"candidates": [{"name": "Dave McCormick", "code": "R"}, {"name": "Bob Casey Jr.", "code": "D"}]})
        res = p["results"] or {}; top = (res.get("candidates") or [{}])[0]
        return res.get("winner") == "Dave McCormick" and top.get("votes") == 3399295, \
            f"winner {res.get('winner')} with {top.get('votes'):,} votes ({top.get('pct')}%), '{res.get('status')}'; {len((p['aggregates'] or {}).get('rows', []))} polling-average rows; {len(p['photos'])} photos"
    def t_gov():
        rs, rev = summ("2024 United States gubernatorial elections", "governor", "governor")
        w = [r for r in rs if any(c["winner"] for c in r["candidates"])]
        nc = next((c["name"] for r in rs if r["state"] == "NC" for c in r["candidates"] if c["winner"]), None)
        return len(w) >= 11 and nc == "Josh Stein", f"{len(rs)} rows parsed, {len(w)} with a winner marked; North Carolina winner = {nc}"
    def t_nc():
        f = nc_feed("20241105"); g = next((c for c in f["contests"] if c["kind"] == "governor"), None); h = [c for c in f["contests"] if c["kind"] == "house"]
        lead = g["options"][0]
        return lead["name"] == "Josh Stein" and g["reporting"] == g["total_units"] and len(h) == 14, \
            f"governor: {lead['name']} {lead['votes']:,} votes ({lead['pct']}%), {g['reporting']:,} of {g['total_units']:,} precincts; {len(h)} House contests"
    def t_ga():
        d = get(f"{EV}/elections/Georgia/2024NovGen/data", timeout=90)
        h = [b for b in d["ballotItems"] if (contest_kind(b["name"][0]["text"]) or ("",))[0] == "house"]
        rs = h[0]["reportingStatus"] if h else {}
        return len(h) == 14 and rs.get("reportingUnits") == rs.get("totalUnits"), f"{len(h)} House contests; District 1: {rs.get('reportingUnits')} of {rs.get('totalUnits')} counties reporting, state time stamp {rs.get('asOf')}"
    def t_2026():
        f = build_official()["feeds"]; s = []
        for st, x in f.items():
            if not x.get("ok"): s.append(f"{st}: error"); continue
            s.append(f"{st}: " + (f"{len(x['contests'])} contests armed, 0 votes yet" if x.get("published") else "not listed yet"))
        return all(x.get("ok") for x in f.values()), "; ".join(s)
    ck("Wikipedia 2024 Senate summary: winners", t_sen)
    ck("Wikipedia 2024 race article: vote totals", t_page)
    ck("Wikipedia 2024 governor summary: winners", t_gov)
    ck("North Carolina State Board of Elections, 2024 file", t_nc)
    ck("Georgia Secretary of State (Enhanced Voting), 2024 data", t_ga)
    ck("2026 official feeds reachable", t_2026)
    rep["ok"] = all(c["ok"] for c in rep["checks"])
    return rep

# ------------------------------------------------------------------ box loop
def cycle(state):
    t = time.time(); night = election_night()
    base_every = 600 if night else 3 * 3600
    if t - state.get("base", 0) > base_every:
        try:
            d = build_base(load_base() or {}, race_pages=True); store_base(d); state["base"] = state["summ"] = t
            log("base ok", d["counts"], f"{_NET['req']} requests, {_NET['bytes'] // 1024} KB so far")
        except Exception as e: log("base failed", repr(e)); state["base"] = t - base_every + 600
    elif night and t - state.get("summ", 0) > 240:   # summary articles only (winners, balance); race pages reused
        try: d = build_base(load_base() or {}, race_pages=False); store_base(d); log("summary ok")
        except Exception as e: log("summary failed", repr(e))
        state["summ"] = t
    if t - state.get("odds", 0) > 900:
        b = load_base()
        if b:
            try: put("odds", build_odds(b["races"])); log("odds ok")
            except Exception as e: log("odds failed", repr(e))
            state["odds"] = t
    if t - state.get("off", 0) > (110 if night else 1800):
        try: put("official", build_official()); log("official ok")
        except Exception as e: log("official failed", repr(e))
        state["off"] = t
    if t - state.get("test", 0) > 12 * 3600:
        try: put("pipeline_test", pipeline_test())
        except Exception as e: log("test failed", repr(e))
        state["test"] = t
def main_loop():
    state = {}
    while True:
        try: cycle(state)
        except Exception as e: log("cycle error", repr(e))
        time.sleep(20)

# ------------------------------------------------------------------ web (box + public node)
FILES = {"app.js": "application/javascript", "app.css": "text/css", "states.geojson": "application/geo+json"}
_L = {"lock": threading.Lock(), "official": None, "official_at": 0, "busy": False, "base_mt": None, "base": None}
def _official_bg():
    try:
        d = build_official()
        with _L["lock"]: _L["official"] = d
    except Exception: pass
    finally: _L["busy"] = False
def _age(ts):
    try: return (now() - datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds()
    except Exception: return 1e9
def official():
    db, _ = rget("official"); mine = _L["official"]; best = db
    if mine and (not db or mine.get("fetched", "") > db.get("fetched", "")): best = mine
    if election_night() and not _L["busy"] and _age((best or {}).get("fetched")) > 150 and time.time() - _L["official_at"] > 120:
        _L["busy"] = True; _L["official_at"] = time.time()
        threading.Thread(target=_official_bg, name="midterms-official", daemon=True).start()
    return best
def _base():
    try: mt = os.path.getmtime(DB)
    except OSError: return None
    with _L["lock"]:
        if _L["base_mt"] == mt and _L["base"]: return _L["base"]
    b = load_base()
    if b:
        with _L["lock"]: _L["base_mt"] = mt; _L["base"] = b
    return b
def summary():
    b = _base()
    if not b: return 503, {"error": "Midterms data has not synced yet. It is built on the scanner node from public sources and pushed to the site every few minutes."}
    odds, _ = rget("odds"); test, _ = rget("pipeline_test")
    return 200, {**b, "odds": odds, "pipeline_test": test, "poll_close_source": POLL_CLOSE_SRC, "first_close": FIRST_CLOSE, "last_close": LAST_CLOSE,
                 "official_links": OFFICIAL_LINKS, "official_live": official(), "official_feeds": {k: {"source": v, "url": EV_STATES[k][1]} for k, v in EV_LABEL.items()} | {"NC": {"source": "North Carolina State Board of Elections", "url": "https://er.ncsbe.gov/"}},
                 "night": {"start": NIGHT_START.isoformat(), "end": NIGHT_END.isoformat(), "active": election_night()}, "server_time": iso(),
                 "label": "Descriptive only: ratings, polls, market prices and results are shown as published by the cited sources."}
def live():
    """Small payload for the election-night auto-refresh: official feeds + Wikipedia-recorded winners/status + balance of power."""
    b = _base() or {}; wk = {}
    for r in (b.get("races") or []) + (b.get("house") or []):
        res = (r.get("page") or {}).get("results") or {}
        w = [c["name"] for c in r["candidates"] if c.get("winner")]
        pv = [{"name": c["name"], "code": c.get("code"), "votes": c["votes"], "pct": c["pct"]} for c in res.get("candidates", []) if c.get("votes")][:6]
        if w or res.get("winner") or pv or any(c.get("pct") for c in r["candidates"]):
            wk[r["id"]] = {"winners": w, "status": r.get("status"), "pct": {c["name"]: c["pct"] for c in r["candidates"] if c.get("pct") is not None},
                           "page_winner": res.get("winner"), "page_status": res.get("status"), "page_votes": pv}
    return 200, {"server_time": iso(), "night": election_night(), "official": official(), "wikipedia": wk, "balance": b.get("balance"),
                 "sources": b.get("sources"), "built": b.get("built")}
def handle_get(path, qs):
    if path.startswith("/api/midterms/") and os.path.basename(path) in FILES:
        with open(os.path.join(STATIC, os.path.basename(path)), "rb") as fh: return 200, fh.read(), FILES[os.path.basename(path)]
    if path == "/api/midterms": return summary()
    if path == "/api/midterms/live": return live()
    if path in ("/midterms", "/midterms/", "/election", "/elections"):   # seo/batch-2: real server-rendered hub (midterms_hub.py), self-canonical /midterms
        import midterms_hub; return midterms_hub.handle(path)
    return 404, {"error": "not found"}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "once"
    if cmd == "loop": main_loop()
    elif cmd == "once":
        d = build_base(load_base() or {}); store_base(d); log("base", d["counts"], f"{_NET['req']} requests")
        put("odds", build_odds(d["races"])); log("odds")
        put("official", build_official()); log("official")
    elif cmd == "test":
        r = pipeline_test(); put("pipeline_test", r); print(json.dumps(r, indent=1)); sys.exit(0 if r["ok"] else 1)
    elif cmd == "official": put("official", build_official()); print(json.dumps(rget("official")[0], indent=1)[:4000])
