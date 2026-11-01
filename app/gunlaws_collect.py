#!/usr/bin/env python3
"""Gun Laws tab collector (box only). Writes ONLY gunlaws.db (+ a box-local download cache in logs/gunlaws_cache/).
render_sync.py pushes gunlaws.db to the public site like every other top-level *.db; gunlaws.py serves it read-only.

Daily (full refresh):
  * Supreme Court: the latest "SCOTUS Gun Watch" table from the Duke Center for Firearms Law (every pending, granted and denied
    firearms petition this term) + the curated dockets in gunlaws_curated.py, each hydrated from the Court's own docket JSON
    (https://www.supremecourt.gov/RSS/Cases/JSON/<no>.json): parties, counsel of record (name + firm only), amici, docket entries,
    next conference / argument / response dates, question presented.
  * Lower courts and ballot measures: gunlaws_curated.py (hand-checked, with links).
  * Federal bills: GovInfo BILLSTATUS bulk XML for the current Congress (official Congress.gov data, keyless) filtered to firearms
    bills; base rates for "becomes law" by stage from the two previous Congresses at the same point in the term.
  * SCOTUS reversal rates: Ballotpedia's "SCOTUS case reversal rates" tables.
  * Prediction markets: a sweep of every open Kalshi event and Polymarket search/tags for firearms topics.
Hourly: market prices + price history (Kalshi candlesticks, Polymarket CLOB prices-history) + our own hourly snapshot, then the model.
Every source is free and public; no accounts, no keys; nothing is invented (missing values are stored as null and shown as "not published").

Usage: python3 gunlaws_collect.py once | markets | loop | status
"""
import html, io, json, math, os, random, re, sqlite3, sys, time, traceback, urllib.parse, urllib.request, urllib.error, zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, date, timedelta

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
import gunlaws_curated as CUR
DB = os.path.join(BASE, "gunlaws.db")
CACHE = os.path.join(BASE, "logs", "gunlaws_cache")
LOG = os.path.join(BASE, "logs", "gunlaws.log")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 blackout.network-gunlaws-tab/1.0 (daily public-record refresh)"
KS = "https://api.elections.kalshi.com/trade-api/v2"; PM = "https://gamma-api.polymarket.com"; CLOB = "https://clob.polymarket.com"
SC_JSON = "https://www.supremecourt.gov/RSS/Cases/JSON/{}.json"
CONGRESS = 119; CONG_START = {117: date(2021, 1, 3), 118: date(2023, 1, 3), 119: date(2025, 1, 3)}; CONG_END = {117: date(2023, 1, 3), 118: date(2025, 1, 3), 119: date(2027, 1, 3)}
FIRE_RX = re.compile(r"\b(fire ?arms?|guns?|handguns?|rifles?|shotguns?|pistols?|ammunition|second amendment|2nd amendment|concealed carry|carry reciprocity|suppressors?|silencers?|"
                     r"nics|background checks?|ghost guns?|bump stocks?|machine ?guns?|assault weapons?|semi-?automatic|magazines? (?:limit|ban)|large[- ]capacity|"
                     r"extreme risk|red flag|bureau of alcohol, tobacco|\batf\b|shooting ranges?|national firearms act|gun-free|stabilizing braces?|pistol braces?|"
                     r"firearm|armed|right to bear)\b", re.I)
NOT_GUN_RX = re.compile(r"\b(armed forces|armed services|gunnison|shotgun stage)\b", re.I)
OMNIBUS_RX = re.compile(r"appropriations|reconciliation|national defense authorization|continuing appropriations|providing for consideration|"
                        r"an act to provide for reconciliation|consolidated appropriations|extensions act", re.I)
MKT_RX = re.compile(r"\b(guns?|firearms?|second amendment|2nd amendment|ar-15|ar15|assault weapons?|rifles?|handguns?|pistols?|bear arms|ammunition|nra|atf|"
                    r"magazine limit|bruen|concealed carry|state gun)\b", re.I)
MKT_EXCL = re.compile(r"gunma|gunna|skygunners|young thug|top gun|gunners|nhl|ncaa|nfl|nba|mlb|ufc|fantasy|oscar|grammy|movie|box office|album|song", re.I)

def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def log(m):
    os.makedirs(os.path.dirname(LOG), exist_ok=True); line = time.strftime("[%Y-%m-%dT%H:%M:%SZ] ", time.gmtime()) + m
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")
_last = {}
def get(url, timeout=45, delay=0.0, raw=False, accept="*/*"):
    host = urllib.parse.urlsplit(url).netloc
    if delay:
        w = _last.get(host, 0) + delay - time.time()
        if w > 0: time.sleep(w)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r: b = r.read(); break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 2: raise
            time.sleep(10 * (attempt + 1))
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if attempt == 2: raise
            time.sleep(5 * (attempt + 1))
    _last[host] = time.time()
    return b if raw else b.decode("utf-8", "replace")
def jget(url, **kw): return json.loads(get(url, accept="application/json", **kw))
def strip(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

# ------------------------------------------------------------------ db
def db():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS snaps (mid TEXT, ts INTEGER, p REAL, PRIMARY KEY (mid, ts))")
    return c
def mset(c, k, v): c.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, json.dumps(v, ensure_ascii=False, separators=(",", ":"))))
def mget(c, k, d=None):
    r = c.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
    return json.loads(r[0]) if r else d

# ------------------------------------------------------------------ statistics (stdlib only)
def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 300, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1, a - 1; c = 1.0; d = 1 - qab * x / qap
    d = 1 / (d if abs(d) > FPMIN else FPMIN); h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m; aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = FPMIN if abs(d) < FPMIN else d; c = 1 + aa / c; c = FPMIN if abs(c) < FPMIN else c; d = 1 / d; h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = FPMIN if abs(d) < FPMIN else d; c = 1 + aa / c; c = FPMIN if abs(c) < FPMIN else c; d = 1 / d; de = d * c; h *= de
        if abs(de - 1) < EPS: break
    return h
def betainc(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    return bt * _betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - bt * _betacf(b, a, 1 - x) / b
def betaq(a, b, q):
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if betainc(a, b, mid) < q: lo = mid
        else: hi = mid
    return (lo + hi) / 2
def jeffreys(k, n):
    """Jeffreys estimate of a rate: mean (k+1/2)/(n+1), 90% interval from Beta(k+1/2, n-k+1/2)."""
    a, b = k + 0.5, n - k + 0.5
    return {"k": k, "n": n, "p": round(a / (a + b), 4), "lo": round(betaq(a, b, 0.05), 4), "hi": round(betaq(a, b, 0.95), 4)}
def logit(p): p = min(max(p, 1e-4), 1 - 1e-4); return math.log(p / (1 - p))
def inv(x): return 1 / (1 + math.exp(-x))
def norm_cdf(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))
def combine(parts, draws=20000, seed=319):
    """Weighted log-odds average of component probabilities. 90% interval = 5th-95th percentile of the combined value when each
    component is redrawn from its own uncertainty (Beta posterior for base rates, bid-ask range for markets, normal for polls)."""
    parts = [p for p in parts if p.get("p") is not None and p.get("w")]
    if not parts: return None
    W = sum(p["w"] for p in parts)
    est = inv(sum(p["w"] * logit(p["p"]) for p in parts) / W)
    rng = random.Random(seed); vals = []
    for _ in range(draws):
        s = 0.0
        for p in parts:
            d = p.get("dist") or ("fixed",)
            if d[0] == "beta": x = rng.betavariate(d[1], d[2])
            elif d[0] == "uniform": x = rng.uniform(d[1], d[2])
            elif d[0] == "normcdf": x = norm_cdf((rng.gauss(d[1], d[2]) - 0.5) / d[3]) if d[3] else (1.0 if rng.gauss(d[1], d[2]) > .5 else 0.0)
            else: x = p["p"]
            s += p["w"] * logit(x)
        vals.append(inv(s / W))
    vals.sort()
    return {"p": round(est, 4), "lo": round(vals[int(.05 * draws)], 4), "hi": round(vals[int(.95 * draws) - 1], 4), "weights": {p["key"]: round(p["w"] / W, 3) for p in parts}}

# ------------------------------------------------------------------ Supreme Court
def duke_latest():
    """Latest weekly 'SCOTUS Gun Watch' post URL from the Duke Center's blog index."""
    t = get("https://firearmslaw.duke.edu/secondthoughts", delay=2)
    links = sorted(set(re.findall(r'href="(/20\d\d/\d\d/scotus-gun-watch-(\d{1,2})-(\d{1,2})-(20\d\d))"', t)), key=lambda x: (int(x[3]), int(x[1]), int(x[2])), reverse=True)
    if not links: raise RuntimeError("no SCOTUS Gun Watch link on the Duke blog index")
    l = links[0]; return "https://firearmslaw.duke.edu" + l[0], f"{l[3]}-{int(l[1]):02d}-{int(l[2]):02d}"
def duke_table(url):
    t = get(url, delay=2); rows = []
    for ti, tb in enumerate(re.findall(r"<table.*?</table>", t, re.S)):
        section = ""
        for r in re.findall(r"<tr.*?</tr>", tb, re.S):
            cells = [strip(c) for c in re.findall(r"<t[dh].*?</t[dh]>", r, re.S)]
            if len(cells) == 1 or (len(cells) > 1 and not any(cells[1:])): section = cells[0]; continue
            if len(cells) < 5 or cells[1] in ("Case Number", ""): continue
            m = re.search(r"\b(\d{2}-\d{1,5}|\d{2}A\d{1,4})\b", cells[1])
            if not m: continue
            rows.append({"name": cells[0], "docket": m.group(1), "from": cells[2], "issue": cells[3], "status": cells[4], "section": section, "table": ti})
    return rows
def ifp(docket): m = re.match(r"\d{2}-(\d+)$", docket); return bool(m and int(m.group(1)) >= 5000)
MON = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
def sc_date(s):
    m = re.match(r"([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{4})", s or "")
    return f"{m.group(3)}-{MON[m.group(1)]:02d}-{int(m.group(2)):02d}" if m and m.group(1) in MON else None
def us_date(s):
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s or "")
    if not m: return None
    y = int(m.group(3)); y = y + 2000 if y < 100 else y
    return f"{y}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
LONG = r"(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (\d{4})"
def long_date(s):
    m = re.search(LONG, s or "")
    if not m: return None
    return f"{m.group(3)}-{['January','February','March','April','May','June','July','August','September','October','November','December'].index(m.group(1))+1:02d}-{int(m.group(2)):02d}"
def qp_text(d):
    """Question presented from the Court's QP PDF (pdftotext on the box); None if unavailable."""
    link = d.get("QPLink")
    if not link: return None
    url = urllib.parse.urljoin("https://www.supremecourt.gov/docket/docketfiles/html/public/", link)
    try:
        b = get(url, raw=True, delay=1.0)
        p = os.path.join(CACHE, "qp.pdf"); open(p, "wb").write(b)
        import subprocess
        t = subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True, timeout=30).stdout
        t = re.sub(r"[ \t]+", " ", t)
        m = re.search(r"QUESTIONS? PRESENTED:?\s*(.*?)(?:\n\s*(?:THE MOTION|THE PETITION|PETITIONS? GRANTED|CERT\.|LOWER COURT CASE|CONSOLIDATED)|$)", t, re.S)
        q = re.sub(r"\s+", " ", (m.group(1) if m else "")).strip()
        g = re.search(r"(GRANTED LIMITED TO[^\n]*(?:\n[^\n]+){0,4}|GRANTED AS TO THE QUESTION[^\n]*)", t)
        return {"qp": q[:1500] or None, "limited": re.sub(r"\s+", " ", g.group(1)).strip()[:600] if g else None, "url": url}
    except Exception as e:
        return {"qp": None, "limited": None, "url": url, "error": str(e)[:120]}
def sc_docket(no):
    d = jget(SC_JSON.format(no), delay=1.2)
    procs = d.get("ProceedingsandOrder") or []
    entries = []
    for p in procs:
        links = [{"d": l.get("Description"), "u": l.get("DocumentUrl")} for l in (p.get("Links") or []) if (l.get("DocumentUrl") or "").startswith("https://")][:2]
        entries.append({"date": sc_date(p.get("Date")), "text": strip(p.get("Text"))[:400], "links": links})
    txt = " | ".join(e["text"] for e in entries)
    status, stage, nxt, nxt_label = "Petition pending", "pending", None, None
    today = date.today().isoformat()
    dec = [e for e in entries if re.search(r"Judgment (REVERSED|AFFIRMED|VACATED)|Adjudged to be (AFFIRMED|REVERSED)|REVERSED and|VACATED and", e["text"])]
    den = [e for e in entries if re.search(r"Petition DENIED", e["text"], re.I)]
    gvr = [e for e in entries if re.search(r"GRANTED\. The judgment is VACATED", e["text"])]
    gr = [e for e in entries if re.search(r"Petition GRANTED|petition for a writ of certiorari is granted", e["text"], re.I)]
    arg = [e for e in entries if e["text"].startswith("Argued")]
    setarg = [e for e in entries if "SET FOR ARGUMENT" in e["text"]]
    if no.startswith(tuple(f"{y}A" for y in range(20, 40))) or re.match(r"\d{2}A\d+", no):
        stage = "application"; status = "Application to extend time to file a petition"
        m = re.findall(r"extending the time to file until " + LONG, txt)
        if m: nxt = long_date(" ".join(m[-1])); nxt_label = "Petition deadline"; status = f"Time to file a petition extended to {m[-1][0]} {m[-1][1]}, {m[-1][2]}"
    elif dec: stage, status = "decided", "Decided " + (dec[-1]["date"] or "")
    elif gvr: stage, status = "gvr", "Granted, vacated and remanded " + (gvr[-1]["date"] or "")
    elif den: stage, status = "denied", "Petition denied " + (den[-1]["date"] or "")
    elif arg: stage, status = "argued", "Argued " + (arg[-1]["date"] or "") + "; decision pending"
    elif gr:
        stage, status = "granted", "Review granted " + (gr[-1]["date"] or "")
        if setarg:
            m = re.search(r"SET FOR ARGUMENT on \w+, " + LONG, setarg[-1]["text"])
            if m: nxt = long_date(setarg[-1]["text"]); nxt_label = "Oral argument"; status += f"; argument {m.group(1)} {m.group(2)}, {m.group(3)}"
    if stage == "pending":
        dist = [e for e in entries if e["text"].startswith("DISTRIBUTED for Conference of")]
        resc = [e for e in entries if e["text"].startswith("Rescheduled")]
        resp = re.findall(r"Response Requested\.?\s*\(Due " + LONG + r"\)", txt)
        ext = re.findall(r"extended to and including " + LONG, txt)
        due = re.findall(r"\(Response due " + LONG + r"\)", txt)
        last = dist[-1] if dist else None
        conf = us_date(last["text"]) if last else None
        lt = lambda t: long_date(f"{t[0]} {t[1]}, {t[2]}")
        dues = [d for d in [lt(x) for x in ext + due + resp] if d]
        fut = max(dues) if dues and max(dues) >= today else None
        if last and conf and conf >= today and not (resc and resc[-1]["date"] and last["date"] and resc[-1]["date"] >= last["date"] and conf <= (resc[-1]["date"] or "")):
            status = f"Distributed for the {conf} conference"; nxt, nxt_label = conf, "Conference"
        elif fut:
            status = (f"Court requested a response; due {fut}" if resp else f"Response due {fut}"); nxt, nxt_label = fut, "Response due"
        elif last and conf and conf < today:
            status = f"Last distributed for the {conf} conference" + ("; rescheduled" if resc else "") + "; no order yet"
        elif dues:
            status = f"Response was due {max(dues)}; not yet distributed"
        if any(e["text"].startswith("Waiver of right of respondent") for e in entries) and nxt_label != "Conference" and not resp: status += " (respondent waived a response)"
        if resp: status = status if "requested" in status else status + "; the Court had requested a response"
    relisted = sum(1 for e in entries if e["text"].startswith("DISTRIBUTED for Conference"))
    def cnl(lst, header):
        out = []
        for a in lst or []:
            out.append({"name": a.get("Attorney"), "firm": a.get("Title"), "party": a.get("PartyName"), "of_record": bool(a.get("IsCounselofRecord"))})
        return out
    pet, resp_c, other = cnl(d.get("Petitioner"), "p"), cnl(d.get("Respondent"), "r"), cnl(d.get("Other"), "o")
    amici = sorted({re.sub(r"\s+", " ", (e["text"].split("Brief amici curiae of ")[-1].split("Brief amicus curiae of ")[-1].split("Amicus brief of ")[-1]))
                    .replace(" filed.", "").replace(" submitted.", "").replace("(Distributed)", "").strip()[:220]
                    for e in entries if re.search(r"(Brief amic\w+ curiae of|Amicus brief of)", e["text"])})
    return {"docket": no.strip(), "pet": strip(d.get("PetitionerTitle")), "resp": strip(d.get("RespondentTitle")), "docketed": long_date(d.get("DocketedDate")),
            "lower": d.get("LowerCourt"), "lower_no": (d.get("LowerCourtCaseNumbers") or "").strip("() "), "lower_date": long_date(d.get("LowerCourtDecision")),
            "ifp": d.get("sJsonCaseType") == "IFP" or ifp(no), "related": [r.get("DisplayCaseNumber") for r in d.get("RelatedCaseNumber") or []],
            "status": status, "stage": stage, "next": nxt, "next_label": nxt_label, "times_distributed": relisted,
            "counsel": {"petitioner": pet, "respondent": resp_c}, "other_counsel": other, "amici": amici,
            "entries": entries[-14:], "n_entries": len(entries), "qp_link": d.get("QPLink"),
            "url": f"https://www.supremecourt.gov/search.aspx?filename=/docket/docketfiles/html/public/{no}.html",
            "json_url": SC_JSON.format(no), "fetched": now()}

def collect_scotus(c):
    src = {}
    try:
        url, wk = duke_latest(); rows = duke_table(url)
        src["duke"] = {"url": url, "week": wk, "rows": len(rows), "ok": True}
    except Exception as e:
        rows = []; url = None; src["duke"] = {"ok": False, "error": str(e)[:200]}
        prev = mget(c, "scotus_rows") or []; rows = prev
    try:   # scotus2a.com: docket numbers it tracks (union with the Duke table and the curated list)
        t = get("https://scotus2a.com/", delay=2); s2a = sorted(set(re.findall(r"No\.\s*(\d{2}-\d{1,5}|\d{2}A\d{1,4})", t)))
        src["scotus2a"] = {"url": "https://scotus2a.com/", "dockets": s2a, "ok": True}
    except Exception as e: s2a = []; src["scotus2a"] = {"ok": False, "error": str(e)[:200]}
    mset(c, "scotus_rows", rows)
    pend = [r for r in rows if not re.match(r"(Denied|GVR|Granted)", r["status"], re.I) and r["section"] != "Voluntary Dismissals"]
    want = list(dict.fromkeys(list(CUR.SCOTUS) + s2a + [r["docket"] for r in pend] + [r["docket"] for r in rows if r["status"].lower().startswith("granted")]))
    old = {x["docket"]: x for x in (mget(c, "scotus") or [])}
    out = []; errs = 0
    for no in want:
        try:
            x = sc_docket(no)
            cached = old.get(no) or {}
            if cached.get("qp") and cached.get("n_entries") == x["n_entries"]: x["qp"] = cached["qp"]
            else: x["qp"] = qp_text({"QPLink": x["qp_link"]}) if x["qp_link"] else None
        except Exception as e:
            errs += 1; log(f"scotus {no}: {e}")
            if no in old: x = old[no]; x["stale"] = True
            else: continue
        r = next((r for r in rows if r["docket"] == no), None)
        if r: x["duke"] = {"issue": r["issue"], "status": r["status"], "from": r["from"], "section": r["section"]}
        cu = CUR.SCOTUS.get(no)
        if cu: x["cur"] = cu
        x["short"] = (cu or {}).get("short") or (r or {}).get("name") or (x["pet"].split(",")[0] + " v. " + x["resp"].split(",")[0])
        x["topic"] = topic_of(" ".join([(cu or {}).get("law", ""), (r or {}).get("issue", ""), ((x.get("qp") or {}).get("qp") or "")]), (cu or {}).get("group"))
        x["state"] = (cu or {}).get("state") or state_of(x.get("lower") or "", x["resp"])
        out.append(x)
    # tally of this term's firearms petitions (Duke table) for the cert-grant base rate
    dec = [r for r in rows if re.match(r"(Denied|GVR|Granted)", r["status"], re.I)]
    tally = {"paid": {"granted": 0, "decided": 0}, "ifp": {"granted": 0, "decided": 0}}
    for r in dec:
        k = "ifp" if ifp(r["docket"]) else "paid"; tally[k]["decided"] += 1
        if r["status"].lower().startswith("granted"): tally[k]["granted"] += 1
    src["tally"] = tally
    mset(c, "scotus", out); mset(c, "scotus_src", src)
    log(f"scotus: {len(out)} dockets ({errs} errors), duke rows {len(rows)}, tally {tally}")
    return out

TOPICS = [("rifles", r"ar-15|semi-?automatic (rifle|assault)|assault (weapon|firearm|-style)|rifle"), ("magazines", r"magazine|feeding device"),
          ("carry", r"sensitive place|carry|parks?\b|licens"), ("who may own", r"922\(g\)|felon|felony|unlawful user|indictment|922\(n\)|alien|noncitizen|misdemeanor|dui|protection order|restraining order|age\b|18-to-20|under 21"),
          ("other arms", r"stun gun|taser|machine ?gun|silencer|suppressor|short-barrel"), ("commerce/sales", r"commerce clause|interstate|crossed state lines|sale|purchase|dealer")]
def topic_of(t, given=None):
    if given: return given
    for k, rx in TOPICS:
        if re.search(rx, t or "", re.I): return k
    return "other"
STATE_NAMES = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
               "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA",
               "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
               "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
               "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY"}
def state_of(lower, resp):
    for n, a in STATE_NAMES.items():
        if re.search(r"\b" + n + r"\b", lower) and "Circuit" not in lower: return a
    for n, a in STATE_NAMES.items():
        if re.search(r"\b" + n + r"\b", resp or ""): return a
    return None

def collect_reversal(c):
    """Ballotpedia: SCOTUS decisions by circuit, by term (affirmed / reversed)."""
    try:
        t = get("https://ballotpedia.org/SCOTUS_case_reversal_rates_(2007_-_Present)", delay=3)
        terms = []
        for tb in re.findall(r"<table.*?</table>", t, re.S):
            rows = [[strip(x) for x in re.findall(r"<t[dh].*?</t[dh]>", r, re.S)] for r in re.findall(r"<tr.*?</tr>", tb, re.S)]
            if not rows or not rows[0] or not re.match(r"SCOTUS decisions by circuit, (\d{4})", rows[0][0]): continue
            yr = int(re.match(r"SCOTUS decisions by circuit, (\d{4})", rows[0][0]).group(1)); by = {}
            for r in rows[2:]:
                if len(r) >= 4 and r[1].isdigit(): by[r[0]] = {"decided": int(r[1]), "affirmed": int(r[2]), "reversed": int(r[3])}
            if "Total" in by: terms.append({"term": yr, "by": by})
        terms.sort(key=lambda x: -x["term"])
        if terms:
            mset(c, "reversal", {"terms": terms[:6], "url": "https://ballotpedia.org/SCOTUS_case_reversal_rates_(2007_-_Present)", "fetched": now()})
            log(f"reversal: {len(terms)} terms, latest {terms[0]['term']} total {terms[0]['by']['Total']}")
    except Exception as e: log(f"reversal: {e}")

# ------------------------------------------------------------------ federal bills (GovInfo BILLSTATUS bulk)
def bulk_zip(cong, t, max_age_h=20):
    os.makedirs(CACHE, exist_ok=True); p = os.path.join(CACHE, f"BILLSTATUS-{cong}-{t}.zip")
    if os.path.exists(p) and (cong < CONGRESS or time.time() - os.path.getmtime(p) < max_age_h * 3600): return p
    b = get(f"https://www.govinfo.gov/bulkdata/BILLSTATUS/{cong}/{t}/BILLSTATUS-{cong}-{t}.zip", raw=True, timeout=600)
    open(p + ".tmp", "wb").write(b); os.replace(p + ".tmp", p); return p
def iter_bills(cong):
    for t in ("hr", "s", "hjres", "sjres"):
        z = zipfile.ZipFile(bulk_zip(cong, t))
        for n in z.namelist():
            if n.endswith(".xml"):
                b = ET.fromstring(z.read(n)).find("bill")
                if b is not None: yield b
STAGES = ["introduced", "reported", "passed_one", "passed_both", "law"]
STAGE_LABEL = {"introduced": "Introduced (in committee)", "reported": "Reported by committee / on the calendar", "passed_one": "Passed one chamber",
               "passed_both": "Passed both chambers", "law": "Became law", "vetoed": "Vetoed"}
def acts(b):
    out = []
    for a in b.findall("actions/item"):
        out.append((a.findtext("actionDate") or "", a.findtext("actionCode") or "", a.findtext("type") or "", a.findtext("text") or ""))
    return sorted(out)
def stage_at(al, cutoff=None):
    h = s = rep = law = veto = False; law_d = None
    for d, code, typ, t in al:
        if cutoff and d > cutoff: continue
        if code == "36000" or t.startswith("Became Public Law") or t.startswith("Became Private Law"): law = True; law_d = law_d or d
        if t.startswith("Passed/agreed to in House") or code == "8000": h = True
        if t.startswith("Passed/agreed to in Senate") or code == "17000": s = True
        if code in ("5000", "14000", "H12200", "H12410") or re.match(r"(Reported|Ordered to be Reported|Placed on (the )?(Union|House) Calendar|Placed on Senate Legislative Calendar)", t) or \
           re.search(r"Reported (by|with|without|favorably)|Ordered to be reported", t): rep = True
        if code == "31000" or t.startswith("Vetoed by President"): veto = True
    st = "law" if law else ("passed_both" if (h and s) else ("passed_one" if (h or s) else ("reported" if rep else "introduced")))
    return st, law_d, veto
def is_fire(b):
    subj = [x.text or "" for x in b.findall("subjects/legislativeSubjects/item/name")]
    title = b.findtext("title") or ""
    tag = "Firearms and explosives" in subj
    tm = bool(FIRE_RX.search(title)) and not NOT_GUN_RX.search(title)
    return tag, tm, subj
def base_rates():
    """P(enacted by the end of the Congress | stage reached by the same day of the term), from the 117th and 118th Congresses."""
    off = (date.today() - CONG_START[CONGRESS]).days
    agg = {s: {"n": 0, "k": 0} for s in STAGES[:4]}; fire = {s: {"n": 0, "k": 0} for s in STAGES[:4]}; per = {}
    for cong in (117, 118):
        cutoff = (CONG_START[cong] + timedelta(days=off)).isoformat(); per[cong] = {"cutoff": cutoff}
        for b in iter_bills(cong):
            al = acts(b); st, _, _ = stage_at(al, cutoff)
            if st == "law": continue
            fst, law_d, _ = stage_at(al)
            ok = fst == "law" and law_d and law_d > cutoff
            agg[st]["n"] += 1; agg[st]["k"] += bool(ok)
            tag, tm, _ = is_fire(b)
            if tag or tm:
                fire[st]["n"] += 1; fire[st]["k"] += bool(ok)
    return {"day_of_term": off, "per": per, "all": {s: jeffreys(v["k"], v["n"]) for s, v in agg.items()},
            "firearms": {s: jeffreys(v["k"], v["n"]) for s, v in fire.items()},
            "note": "Bills from the 117th (2021-22) and 118th (2023-24) Congresses, grouped by the furthest stage each had reached on the same day of the two-year term as today; p = share enacted by the end of that Congress (Jeffreys estimate, 90% interval)."}
def collect_bills(c):
    t0 = time.time(); rows = []; enacted_other = []
    for b in iter_bills(CONGRESS):
        tag, tm, subj = is_fire(b)
        if not (tag or tm): continue
        title = b.findtext("title") or ""
        al = acts(b); st, law_d, veto = stage_at(al)
        typ = (b.findtext("type") or "").upper(); num = b.findtext("number")
        omni = bool(OMNIBUS_RX.search(title))
        sp = b.find("sponsors/item")
        cos = b.findall("cosponsors/item"); cos = [x for x in cos if not x.findtext("sponsorshipWithdrawnDate")]
        party = {}
        for x in cos: party[x.findtext("party") or "?"] = party.get(x.findtext("party") or "?", 0) + 1
        sums = b.findall("summaries/summary") or b.findall("summaries/item")
        summ = strip(sums[-1].findtext("text")) if sums else None
        la = b.find("latestAction")
        slug = {"HR": "house-bill", "S": "senate-bill", "HJRES": "house-joint-resolution", "SJRES": "senate-joint-resolution"}.get(typ, "bill")
        cmts = [x.findtext("name") for x in b.findall("committees/item")]
        r = {"id": f"{typ}{num}", "label": {"HR": "H.R.", "S": "S.", "HJRES": "H.J.Res.", "SJRES": "S.J.Res."}.get(typ, typ) + " " + num, "title": title,
             "short": next((x.findtext("title") for x in b.findall("titles/item") if (x.findtext("titleType") or "").startswith("Short Title(s) as Introduced")), None),
             "chamber": "House" if typ.startswith("H") else "Senate", "introduced": b.findtext("introducedDate"),
             "sponsor": {"name": sp.findtext("fullName"), "party": sp.findtext("party"), "state": sp.findtext("state"), "bioguide": sp.findtext("bioguideId")} if sp is not None else None,
             "cosponsors": len(cos), "cos_party": party, "stage": st, "vetoed": veto, "law_date": law_d,
             "latest": {"date": la.findtext("actionDate") if la is not None else None, "text": strip(la.findtext("text")) if la is not None else None},
             "committees": [x for x in cmts if x][:4], "policy": b.findtext("policyArea/name"), "subjects": [s for s in subj if s][:12],
             "crs_tagged": tag, "summary": (summ[:1400] + ("…" if summ and len(summ) > 1400 else "")) if summ else None,
             "url": f"https://www.congress.gov/bill/{CONGRESS}th-congress/{slug}/{num}",
             "xml": f"https://www.govinfo.gov/bulkdata/BILLSTATUS/{CONGRESS}/{typ.lower()}/BILLSTATUS-{CONGRESS}{typ.lower()}{num}.xml",
             "omnibus": omni, "updated": b.findtext("updateDate")}
        if omni:
            if st == "law" or tag: enacted_other.append(r)
            continue
        rows.append(r)
    rows.sort(key=lambda r: (-STAGES.index(r["stage"]), -(r["cosponsors"] or 0), r["id"]))
    br = mget(c, "bill_rates")
    if not br or br.get("day_of_term") != (date.today() - CONG_START[CONGRESS]).days:
        br = base_rates(); mset(c, "bill_rates", br)
    mset(c, "bills", rows); mset(c, "bills_omnibus", [r for r in enacted_other if r["stage"] in ("law", "passed_both", "passed_one")][:30])
    zp = bulk_zip(CONGRESS, "hr")
    mset(c, "bills_src", {"url": f"https://www.govinfo.gov/bulkdata/BILLSTATUS/{CONGRESS}", "fetched": now(), "zip_mtime": datetime.fromtimestamp(os.path.getmtime(zp), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "n": len(rows), "n_crs": sum(r["crs_tagged"] for r in rows)})
    log(f"bills: {len(rows)} firearms bills ({sum(r['crs_tagged'] for r in rows)} CRS-tagged), {len(enacted_other)} omnibus, {time.time()-t0:.0f}s")

# ------------------------------------------------------------------ prediction markets
def ks_markets(event):
    d = jget(f"{KS}/events/{event}?with_nested_markets=true", delay=0.3)
    return d.get("event") or {}
def f(x):
    try: return None if x in (None, "") else float(x)
    except Exception: return None
def ks_mkt(m):
    bid, ask, last = f(m.get("yes_bid_dollars")), f(m.get("yes_ask_dollars")), f(m.get("last_price_dollars"))
    mid = round((bid + ask) / 2, 4) if bid is not None and ask and ask > 0 and ask - bid <= 0.25 else last
    return {"ticker": m.get("ticker"), "name": m.get("yes_sub_title") or m.get("title"), "bid": bid, "ask": ask, "last": last, "mid": mid,
            "volume": f(m.get("volume_fp")), "vol24": f(m.get("volume_24h_fp")), "oi": f(m.get("open_interest_fp")), "status": m.get("status"),
            "close": m.get("close_time"), "rules": (m.get("rules_primary") or "")[:700], "result": m.get("result") or None}
def discover_markets(c):
    """Sweep every open Kalshi event + Polymarket search/tag results; keep firearms-related ones (regex, then exclusions)."""
    found = {}
    try:
        cur = ""; n = 0
        for _ in range(400):
            d = jget(f"{KS}/events?status=open&limit=200" + (f"&cursor={cur}" if cur else ""), delay=0.25)
            for e in d.get("events") or []:
                n += 1; t = f"{e.get('title') or ''} {e.get('sub_title') or ''}"
                if MKT_RX.search(t) and not MKT_EXCL.search(t) and (e.get("category") or "") not in ("Sports", "Entertainment"):
                    found["Kalshi:" + e["event_ticker"]] = {"src": "Kalshi", "event": e["event_ticker"], "series": e.get("series_ticker"), "title": e.get("title"), "sub": e.get("sub_title")}
            cur = d.get("cursor")
            if not cur: break
        log(f"markets: Kalshi sweep {n} open events")
    except Exception as e: log(f"markets: Kalshi sweep failed: {e}")
    for ev in [CUR.BALLOT[0]["market"]["event"], CUR.BALLOT[1]["market"]["event"]]:   # ballot-measure baskets: keep only firearm legs
        found["Kalshi:" + ev] = {"src": "Kalshi", "event": ev, "basket": True}
    try:
        for q in ("gun", "firearm", "second amendment", "AR-15", "assault weapons", "state gun", "concealed carry", "NRA", "ATF"):
            d = jget(f"{PM}/public-search?q={urllib.parse.quote(q)}&limit_per_type=25&events_status=active", delay=0.4)
            for e in d.get("events") or []:
                t = e.get("title") or ""
                if MKT_RX.search(t) and not MKT_EXCL.search(t): found["Polymarket:" + e["slug"]] = {"src": "Polymarket", "slug": e["slug"], "title": t}
        for tag in ("scotus", "supreme-court", "guns", "gun-control", "second-amendment"):
            for e in jget(f"{PM}/events?tag_slug={tag}&closed=false&limit=100", delay=0.4) or []:
                t = e.get("title") or ""
                if MKT_RX.search(t) and not MKT_EXCL.search(t): found["Polymarket:" + e["slug"]] = {"src": "Polymarket", "slug": e["slug"], "title": t}
    except Exception as e: log(f"markets: Polymarket search failed: {e}")
    found.setdefault("Polymarket:" + CUR.BALLOT[2]["pm_event"], {"src": "Polymarket", "slug": CUR.BALLOT[2]["pm_event"]})
    mset(c, "market_index", {"found": found, "at": now(), "searched": {"kalshi": "every open event (title/subtitle regex)", "polymarket": "public-search + scotus/supreme-court/guns tags"}})
    return found
def ks_hist(series, ticker, opened):
    end = int(time.time()); out = []
    for start, per in ((max(opened, end - 400 * 86400), 1440), (end - 7 * 86400, 60)):
        try:
            cs = jget(f"{KS}/series/{series}/markets/{ticker}/candlesticks?start_ts={int(start)}&end_ts={end}&period_interval={per}", delay=0.3).get("candlesticks") or []
        except Exception: cs = []
        for cd in cs:
            pr = cd.get("price") or {}; p = f(pr.get("close_dollars", pr.get("close")))
            if p is None:
                b, a = f((cd.get("yes_bid") or {}).get("close_dollars")), f((cd.get("yes_ask") or {}).get("close_dollars"))
                if b is not None and a and a - b <= .2: p = round((b + a) / 2, 4)
            if p is not None and cd.get("end_period_ts"): out.append((int(cd["end_period_ts"]), round(p, 4)))
    return sorted(dict(out).items())
def pm_hist(token):
    out = []
    for q in ("interval=max&fidelity=1440", "interval=1w&fidelity=60"):
        try:
            h = jget(f"{CLOB}/prices-history?market={token}&{q}", delay=0.3).get("history") or []
            out += [(int(x["t"]), round(float(x["p"]), 4)) for x in h if x.get("p") is not None]
        except Exception: pass
    return sorted(dict(out).items())
FIRE_LEG = re.compile(r"bear arms|firearm|gun|question 9", re.I)
def refresh_markets(c, found=None):
    found = found or (mget(c, "market_index") or {}).get("found") or {}
    if not found: found = discover_markets(c)
    mk = []; ts = int(time.time()) // 3600 * 3600; errs = []
    for key, it in sorted(found.items()):
        try:
            if it["src"] == "Kalshi":
                e = ks_markets(it["event"]); ms = e.get("markets") or []
                if it.get("basket"):
                    ms = [m for m in ms if FIRE_LEG.search((m.get("yes_sub_title") or "") + " " + (m.get("title") or "")) or m.get("ticker") in (CUR.BALLOT[0]["market"]["id"], CUR.BALLOT[1]["market"]["id"])]
                    ms = [m for m in ms if m.get("ticker") in (CUR.BALLOT[0]["market"]["id"], CUR.BALLOT[1]["market"]["id"])]
                ms = [m for m in ms if m.get("status") in ("active", "open", "initialized", "closed", "settled", "determined", "finalized")]
                if not ms: continue
                outs = [ks_mkt(m) for m in ms]
                for o, m in zip(outs, ms):
                    opened = int(datetime.fromisoformat((m.get("open_time") or m.get("created_time") or "2026-01-01T00:00:00Z").replace("Z", "+00:00")).timestamp())
                    o["hist"] = ks_hist(e.get("series_ticker") or it.get("series") or it["event"].split("-")[0], o["ticker"], opened)
                for o in outs:
                    if o["mid"] is not None: c.execute("INSERT OR REPLACE INTO snaps VALUES (?,?,?)", ("Kalshi:" + o["ticker"], ts, o["mid"]))
                title = e.get("title") or it.get("title")
                if it.get("basket"):
                    for o in outs:
                        mk.append({"key": "Kalshi:" + o["ticker"], "src": "Kalshi", "event": it["event"], "title": f"{title}: {o['name']}", "url": f"https://kalshi.com/markets/{(e.get('series_ticker') or '').lower()}",
                                   "outcomes": [o], "multi": False, "settle": e.get("settlement_sources")})
                else:
                    mk.append({"key": key, "src": "Kalshi", "event": it["event"], "title": title, "sub": e.get("sub_title"), "url": f"https://kalshi.com/markets/{(e.get('series_ticker') or '').lower()}",
                               "outcomes": sorted(outs, key=lambda o: -(o["mid"] or 0)), "multi": len(outs) > 1, "settle": e.get("settlement_sources")})
            else:
                es = jget(f"{PM}/events?slug={urllib.parse.quote(it['slug'])}", delay=0.3)
                if not es: continue
                e = es[0]; outs = []
                for m in e.get("markets") or []:
                    try: prices = [float(p) for p in json.loads(m.get("outcomePrices") or "[]")]; toks = json.loads(m.get("clobTokenIds") or "[]")
                    except Exception: continue
                    if not prices or not toks or (float(m.get("volume") or 0) == 0 and prices[0] == 0.5): continue   # unused placeholder legs
                    o = {"ticker": m.get("slug"), "name": m.get("groupItemTitle") or m.get("question"), "mid": round(prices[0], 4), "last": f(m.get("lastTradePrice")),
                         "bid": f(m.get("bestBid")), "ask": f(m.get("bestAsk")), "volume": f(m.get("volume")), "status": "closed" if m.get("closed") else "active",
                         "close": m.get("endDate"), "rules": (m.get("description") or e.get("description") or "")[:700]}
                    o["hist"] = pm_hist(toks[0]); outs.append(o)
                    c.execute("INSERT OR REPLACE INTO snaps VALUES (?,?,?)", ("Polymarket:" + (m.get("slug") or ""), ts, o["mid"]))
                if outs: mk.append({"key": key, "src": "Polymarket", "event": e.get("slug"), "title": e.get("title"), "url": f"https://polymarket.com/event/{e.get('slug')}",
                                    "outcomes": sorted(outs, key=lambda o: -(o["mid"] or 0)), "multi": len(outs) > 1, "volume": f(e.get("volume"))})
        except Exception as ex: errs.append(f"{key}: {ex}"[:160]); log(f"market {key}: {ex}")
    c.execute("DELETE FROM snaps WHERE ts < ?", (int(time.time()) - 400 * 86400,))
    for m in mk:   # attach our own hourly snapshots
        for o in m["outcomes"]:
            o["snaps"] = [list(r) for r in c.execute("SELECT ts, p FROM snaps WHERE mid=? ORDER BY ts", (m["src"] + ":" + (o["ticker"] or ""),))]
    mset(c, "markets", {"items": mk, "at": now(), "errors": errs, "searched": (mget(c, "market_index") or {}).get("searched")})
    log(f"markets: {len(mk)} market groups, {sum(len(m['outcomes']) for m in mk)} outcomes, {len(errs)} errors")
    return mk

# ------------------------------------------------------------------ model
def mk_by_ticker(mk, t):
    for m in mk:
        for o in m["outcomes"]:
            if o.get("ticker") == t: return m, o
    return None, None
def market_part(o, w, label, src):
    if not o or o.get("mid") is None: return None
    b, a = o.get("bid"), o.get("ask")
    dist = ("uniform", b, a) if b is not None and a and a > b else ("fixed",)
    return {"key": "market", "label": label, "p": o["mid"], "w": w, "dist": dist, "src": src,
            "detail": f"mid {o['mid']:.2f}" + (f" (bid {b:.2f} / ask {a:.2f})" if b is not None and a else "") + (f", volume {o['volume']:,.0f}" if o.get("volume") else "")}
def bill_stage_rates(c):
    return (mget(c, "bill_rates") or {}).get("all")
def pm_part(mk, slug_prefix, w, label):
    for m in mk:
        if m["src"] == "Polymarket" and (m.get("event") or "").startswith(slug_prefix) and m["outcomes"]:
            p = market_part(m["outcomes"][0], w, label, m["url"])
            if p: p["key"] = "market_pm"
            return p
    return None
def beta_part(key, label, k, n, w, src, detail=""):
    j = jeffreys(k, n)
    return {"key": key, "label": label, "p": j["p"], "w": w, "dist": ("beta", k + .5, n - k + .5), "src": src, "detail": f"{k} of {n}" + (f"; {detail}" if detail else ""), "rate": j}
def build_model(c):
    mk = (mget(c, "markets") or {}).get("items") or []
    rev = mget(c, "reversal") or {}; terms = (rev.get("terms") or [])[:3]
    out = {"computed": now(), "label": "blackout.network statistical estimate, not legal advice and not a prediction of certainty", "cases": {}, "petitions": {}, "ballot": {}, "bills": {}}
    # --- merits: Viramontes / Grant
    if terms:
        k = sum(t["by"]["Total"]["reversed"] for t in terms); n = sum(t["by"]["Total"]["decided"] for t in terms)
        k7 = sum(t["by"].get("Seventh Circuit", {}).get("reversed", 0) + t["by"].get("Second Circuit", {}).get("reversed", 0) for t in terms)
        n7 = sum(t["by"].get("Seventh Circuit", {}).get("decided", 0) + t["by"].get("Second Circuit", {}).get("decided", 0) for t in terms)
        yrs = ", ".join(str(t["term"]) for t in terms)
    else: k = n = k7 = n7 = 0; yrs = ""
    kd = sum(1 for d in CUR.DECIDED if d["challenger_won"]); nd = len(CUR.DECIDED)
    _, o = mk_by_ticker(mk, "KXSCOTUSAR15-30JAN")
    parts = [p for p in [
        beta_part("reversal", "Supreme Court reverses the lower court (all cases)", k, n, 0.25, rev.get("url"), f"terms {yrs}") if n else None,
        beta_part("bruen", "Challengers' win rate in Second Amendment merits cases since Bruen", kd, nd, 0.25, "supremecourt.gov opinions", "Bruen, Rahimi, Hemani, Wolford"),
        market_part(o, 0.25, "Kalshi: SCOTUS recognizes a right to possess AR-15-style rifles", "https://kalshi.com/markets/kxscotusar15"),
        pm_part(mk, "scotus-invalidates-ar-15-bans", 0.25, "Polymarket: SCOTUS invalidates AR-15 bans (Grant or Viramontes)")] if p]
    if not any(p["key"] == "market_pm" for p in parts):   # only one market available -> it keeps the whole 50% market weight
        for p in parts:
            if p["key"] == "market": p["w"] = 0.5
    if not any(p["key"] == "market" for p in parts):
        for p in parts:
            if p["key"] == "market_pm": p["w"] = 0.5
    comb = combine(parts)
    ctx = {"reversal_2nd_7th": jeffreys(k7, n7) if n7 else None}
    out["cases"]["25-238"] = out["cases"]["25-566"] = {"question": "Will the Court hold that the Second Amendment protects AR-15-platform and similar semiautomatic rifles (challengers win)?",
        "parts": parts, "combined": comb, "context": ctx,
        "plain": (f"Our estimate: about {round(comb['p']*100)}% that the challengers win (90% range {round(comb['lo']*100)}–{round(comb['hi']*100)}%)." if comb else "Not enough inputs."),
        "limits": ["Base rates describe all cases, not this one; the Court picks cases it is more likely to reverse.",
                   "Only four Second Amendment merits decisions since 2022, so that rate is very uncertain.",
                   "Both markets are thin (see volume). Kalshi asks whether the Court recognizes a right to AR-15-style rifles by 2030; Polymarket asks whether Grant or Viramontes invalidates a ban by Aug. 1, 2027. Both resolve No if the cases are dismissed without such a ruling.",
                   "The weights (markets 50% combined, each base rate 25%) are our choice, shown so you can redo the math."]}
    # Beaird: reversal base rate only
    if n:
        p5 = [beta_part("reversal", "Supreme Court reverses or vacates the lower court (all cases)", k, n, 1.0, rev.get("url"), f"terms {yrs}")]
        cb = combine(p5)
        out["cases"]["25-5343"] = {"question": "Will the Court rule for the petitioner (vacate or reverse)?", "parts": p5, "combined": cb,
            "plain": f"Base rate only: about {round(cb['p']*100)}% (90% range {round(cb['lo']*100)}–{round(cb['hi']*100)}%).",
            "limits": ["The Justice Department agrees with the petitioner that the ruling below should be vacated; that is not in the base rate.", "No prediction market exists for this case."]}
    # --- cert petitions: this term's firearms petitions (Duke table)
    tally = (mget(c, "scotus_src") or {}).get("tally") or {}
    for kind in ("paid", "ifp"):
        t = tally.get(kind) or {"granted": 0, "decided": 0}
        out["petitions"][kind] = {"rate": jeffreys(t["granted"], t["decided"]), "label": "paid petitions" if kind == "paid" else "in forma pauperis (fee-waived) petitions",
                                  "src": "Duke Center for Firearms Law, SCOTUS Gun Watch (this term's decided firearms petitions)"}
    # --- nationwide concealed-carry reciprocity (H.R. 38) by Jan. 4, 2027: bill-stage base rate + Kalshi
    try:
        br = bill_stage_rates(c)
        hr38 = next((b for b in (mget(c, "bills") or []) if b["id"] == "HR38"), None)
        _, oc = mk_by_ticker(mk, "KXCONCEALEDRECIPROCITY-27-JAN04")
        if hr38 and br and br.get(hr38["stage"]):
            r = br[hr38["stage"]]
            pc = [p for p in [beta_part("stage", f"119th-Congress-style base rate: bills at stage '{hr38['stage']}' on this day of the term that became law", r["k"], r["n"], 0.5,
                                         "https://www.govinfo.gov/bulkdata/BILLSTATUS", "117th + 118th Congresses"),
                              market_part(oc, 0.5, "Kalshi: nationwide concealed-carry reciprocity becomes law before Jan. 4, 2027", "https://kalshi.com/markets/kxconcealedreciprocity")] if p]
            cc = combine(pc)
            out["cases"]["HR38"] = {"question": "Will nationwide concealed-carry reciprocity (H.R. 38) become law before Jan. 4, 2027?", "parts": pc, "combined": cc,
                "plain": f"Our estimate: about {cc['p']*100:.1f}% (90% range {cc['lo']*100:.1f}–{cc['hi']*100:.1f}%).",
                "limits": ["H.R. 38 was reported by House Judiciary and placed on the Union Calendar (Oct. 3, 2025); it has not had a floor vote.",
                           "The stage base rate covers all bills, not gun bills specifically.", "Weights 50/50 are our choice."]}
    except Exception as ex: log(f"model hr38: {ex}")
    # --- ballot measures
    hf = CUR.BALLOT_HISTORY_FIREARMS
    for bm in CUR.BALLOT:
        m = bm.get("market") or {}
        if m.get("multi"):
            mm = next((x for x in mk if x["src"] == "Kalshi" and x["event"] == m["event"]), None)
            pm = next((x for x in mk if x["src"] == "Polymarket" and x["event"] == bm.get("pm_event")), None)
            out["ballot"][bm["id"]] = {"multi": True, "kalshi": [(o["name"], o["mid"]) for o in (mm or {}).get("outcomes", [])],
                                       "polymarket": [(o["name"], o["mid"]) for o in (pm or {}).get("outcomes", [])],
                                       "plain": "Advisory question with six options: we show market prices only; no statistical model.", "parts": []}
            continue
        _, o = mk_by_ticker(mk, m.get("id"))
        parts = [market_part(o, 0.5, f"Kalshi: {m.get('yes_means')}", "https://kalshi.com/markets/kxstateballotmeasure")]
        polls = [p for p in bm.get("polls") or [] if p.get("end") and (date.today() - date.fromisoformat(p["end"])).days <= 60]
        if polls:
            tw = sum(p["n"] for p in polls); share = sum(p["n"] * p["yes"] / (p["yes"] + p["no"]) for p in polls) / tw
            se = math.sqrt(share * (1 - share) / tw); sigma = 0.06
            pz = norm_cdf((share - 0.5) / math.sqrt(se ** 2 + sigma ** 2))
            parts.append({"key": "polls", "label": f"Polls ({len(polls)} in the last 60 days), two-way yes share", "p": round(pz, 4), "w": 0.3, "dist": ("normcdf", share, se, sigma),
                          "src": bm["links"][0][1], "detail": f"sample-weighted yes share {share*100:.1f}% (n={tw}); assumed polling error σ = 6 points", "share": round(share, 4), "sigma": sigma})
        if bm.get("history"):
            h = bm["history"]; parts.append(beta_part("history", h["label"], h["k"], h["n"], 0.2, h["src"]))
        parts.append(beta_part("firearms_hist", hf["label"], hf["k"], hf["n"], 0.2 if bm.get("history") else 0.5, hf["url"]))
        parts = [p for p in parts if p]
        cb = combine(parts)
        out["ballot"][bm["id"]] = {"question": f"Will {bm['name']} pass (yes wins)?", "parts": parts, "combined": cb,
            "plain": (f"Our estimate: about {round(cb['p']*100)}% that yes wins (90% range {round(cb['lo']*100)}–{round(cb['hi']*100)}%)." if cb else ""),
            "limits": ["Polls of ballot questions can miss by more than their stated margin; the 6-point error is an assumption.", "Market weight 50% (30% when polls exist); weights are ours."]}
    # --- bills
    br = mget(c, "bill_rates") or {}
    out["bills"] = {"rates": br.get("all"), "rates_fire": br.get("firearms"), "note": br.get("note"), "per": br.get("per"), "day_of_term": br.get("day_of_term"),
                    "end": CONG_END[CONGRESS].isoformat()}
    mset(c, "model", out); log("model: computed")
    return out

# ------------------------------------------------------------------ run
def full():
    c = db(); t0 = time.time()
    for name, fn in (("reversal", collect_reversal), ("scotus", collect_scotus), ("bills", collect_bills), ("discover", discover_markets), ("markets", refresh_markets), ("model", build_model)):
        try: fn(c); c.commit()
        except Exception as e: log(f"{name} failed: {e}\n{traceback.format_exc()[-800:]}")
    mset(c, "curated", {"lower": CUR.LOWER, "ballot": CUR.BALLOT, "decided": CUR.DECIDED, "decided_note": CUR.DECIDED_NOTE, "checked": CUR.CHECKED, "ballot_hist": CUR.BALLOT_HISTORY_FIREARMS})
    mset(c, "updated", {"full": now(), "markets": now()}); c.commit(); c.close()
    log(f"full refresh done in {time.time()-t0:.0f}s")
def markets_only():
    c = db()
    try:
        refresh_markets(c); build_model(c); u = mget(c, "updated") or {}; u["markets"] = now(); mset(c, "updated", u); c.commit()
    except Exception as e: log(f"markets refresh failed: {e}")
    c.close()
def loop():
    while True:
        c = db(); u = mget(c, "updated") or {}; c.close()
        last = u.get("full")
        due = not last or (datetime.now(timezone.utc) - datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds() > 24 * 3600
        if due: full()
        else: markets_only()
        time.sleep(3600 - time.time() % 3600 + 120)   # two minutes past each hour
if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["status"])[0]
    if cmd == "once": full()
    elif cmd == "markets": markets_only()
    elif cmd == "loop": loop()
    else:
        c = db(); print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in [("updated", mget(c, "updated")), ("scotus", mget(c, "scotus") or []), ("bills", mget(c, "bills") or [])]}, indent=1))
