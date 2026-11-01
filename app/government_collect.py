#!/usr/bin/env python3
"""Government tab collector (box only; daily). Writes ONLY government.db (+ a box-local cache under logs/gov_cache/).
The public node reads government.db read-only after render_sync.py pushes it (top-level *.db are synced automatically).

Every input is a free, keyless, public source (no accounts, no paid APIs); robots.txt crawl-delays are honoured
(usa.gov and usmayors.org ask for 10 s). Nothing is invented: a value that a source does not publish is stored as NULL and
shown as "no data" / "not published". Photos are only URLs that the source itself publishes; each is checked (HTTP 200 + image
content type) and anything missing/broken gets a labelled initials placeholder in the browser.

Usage: python3 government_collect.py once | loop | rescore | status
"""
import csv, hashlib, html, io, json, os, re, sqlite3, sys, time, traceback, urllib.parse, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, date

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "government.db")
CACHE = os.path.join(BASE, "logs", "gov_cache")
LOG = os.path.join(BASE, "logs", "government.log")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 blackout.network-government-tab/1.0 (daily public-record refresh)"
STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
          "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
          "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
          "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
          "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
          "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
          "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia", "PR": "Puerto Rico", "GU": "Guam", "VI": "U.S. Virgin Islands",
          "AS": "American Samoa", "MP": "Northern Mariana Islands"}
NAME2ST = {v.lower(): k for k, v in STATES.items()}
NAME2ST.update({"virgin islands": "VI", "u.s. virgin islands": "VI", "commonwealth of the northern mariana islands": "MP"})

def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def log(m):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    line = time.strftime("[%Y-%m-%dT%H:%M:%SZ] ", time.gmtime()) + m
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")
_last = {}
def get(url, data=None, timeout=40, delay=0.0, accept="*/*", raw=False, cache_days=0):
    """GET/POST with a per-host politeness delay; optional on-disk cache for immutable files."""
    cp = None
    if cache_days:
        os.makedirs(CACHE, exist_ok=True); cp = os.path.join(CACHE, hashlib.sha1((url + str(data)).encode()).hexdigest())
        if os.path.exists(cp) and time.time() - os.path.getmtime(cp) < cache_days * 86400:
            b = open(cp, "rb").read(); return b if raw else b.decode("utf-8", "replace")
    host = urllib.parse.urlsplit(url).netloc
    if delay:
        w = _last.get(host, 0) + delay - time.time()
        if w > 0: time.sleep(w)
    body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US"})
    for attempt in range(3):   # retry rate limits / transient server errors, backing off
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r: b = r.read(); break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 2: raise
            time.sleep(15 * (attempt + 1))
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:   # transient TLS resets / timeouts
            if attempt == 2: raise
            time.sleep(5 * (attempt + 1))
        finally: _last[host] = time.time()
    if cp: open(cp, "wb").write(b)
    return b if raw else b.decode("utf-8", "replace")
def gj(url, **k): return json.loads(get(url, accept="application/json", **k))
def text(h):
    h = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()
def strip(h): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h or ""))).strip()
STOP = {"the", "of", "and", "for", "on", "u", "s", "us", "united", "states", "department", "dept", "national"}
ALIAS = {"war": "defense"}
def nkey(name):
    n = (name or "").lower().replace("u.s.", "us").replace("&", " and ")
    n = re.sub(r"\(.*?\)", " ", n)
    toks = [ALIAS.get(t, t) for t in re.findall(r"[a-z0-9]+", n) if t not in STOP]
    return " ".join(sorted(set(toks)))
def slug(s): return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:80]

NODES = []; SEEN = set()
def node(id, parent, kind, name, **k):
    if id in SEEN: return id
    SEEN.add(id)
    r = dict(id=id, parent=parent, kind=kind, name=name, title=None, branch=None, state=None, party=None, district=None, photo_url=None,
             photo_credit=None, photo_license=None, photo_status=None, email=None, phone=None, address=None, website=None, contact_form=None,
             about=None, source_label=None, source_url=None, fetched=now(), sort=len(NODES), score_key=None, extra=None)
    for a, b in k.items():
        if a not in r: raise KeyError(a)
        r[a] = b
    if isinstance(r["extra"], (dict, list)): r["extra"] = json.dumps(r["extra"])
    NODES.append(r); return id
SOURCES = {}
def src(key, label, url, license, ok=True, error=None, count=None, as_of=None, note=None):
    SOURCES[key] = dict(label=label, url=url, license=license, fetched=now(), ok=ok, error=error, count=count, as_of=as_of, note=note)

# ------------------------------------------------------------------ executive
USAGOV = {}
def usagov_index():
    """USA.gov A-Z agency index (22 letter pages; robots Crawl-delay 10): description, website, phone, contact page per agency."""
    n = 0
    for L in ["a"] + list("bcdefghijklmnoprstuvw"):
        url = "https://www.usa.gov/agency-index" + ("" if L == "a" else f"/{L}")
        try: h = get(url, delay=10.5)
        except Exception as e: log(f"usa.gov {L}: {e}"); continue
        for blk in h.split('<h2 class="usa-accordion__heading">')[1:]:
            m = re.search(r'<button[^>]*>(.*?)</button>', blk, re.S)
            if not m: continue
            raw = strip(m.group(1)); ab = re.search(r"\(([A-Za-z0-9&\-]{2,12})\)\s*$", raw)
            name = re.sub(r"\s*\([A-Za-z0-9&\-]{2,12}\)\s*$", "", raw).strip()
            body = blk.split("</h2>", 1)[-1]
            p = re.search(r"<p>(.*?)</p>", body, re.S)
            w = re.search(r'field--name-field-website"><a href="([^"]+)"', body)
            ph = re.search(r'field--name-field-phone-number">(.*?)</p>', body, re.S)
            c = re.search(r'field--name-field-contact-link"><a href="([^"]+)"', body)
            mi = re.search(r'href="(/agencies/[^"]+)"', body)
            d = {"name": name, "abbr": ab.group(1) if ab else None, "about": strip(p.group(1)) if p else None, "website": w.group(1) if w else None,
                 "phone": strip(ph.group(1)).split(" ")[0] if ph else None, "contact": urllib.parse.urljoin("https://www.usa.gov", c.group(1)) if c else None,
                 "page": "https://www.usa.gov" + mi.group(1) if mi else url}
            if ph: d["phone"] = strip(ph.group(1))
            USAGOV.setdefault(nkey(name), d); n += 1
            if d["abbr"]: USAGOV.setdefault("abbr:" + d["abbr"].upper(), d)
    src("usagov", "USA.gov A–Z index of U.S. government departments and agencies", "https://www.usa.gov/agency-index", "U.S. government work (public domain)", ok=n > 0, count=n)
def usagov_address(d, budget):
    """Main address from the agency's own USA.gov page (cached 30 days; at most `budget` new fetches per run, 10 s apart)."""
    if not d or not d.get("page", "").startswith("https://www.usa.gov/agencies/"): return None
    os.makedirs(CACHE, exist_ok=True)
    cp = os.path.join(CACHE, "usa_" + hashlib.sha1(d["page"].encode()).hexdigest())
    if os.path.exists(cp) and time.time() - os.path.getmtime(cp) < 30 * 86400: h = open(cp).read()
    elif budget[0] > 0:
        budget[0] -= 1
        try: h = get(d["page"], delay=10.5)
        except Exception: return None
        open(cp, "w").write(h)
    else: return None
    m = re.search(r"Main address (.{5,160}?) (?:SHARE THIS PAGE|Toll-free|Phone|TTY|Website|Find an office|Top|Forms)", text(h))
    return m.group(1).strip() if m else None
def ug(name, abbr=None):
    return USAGOV.get(nkey(name)) or (USAGOV.get("abbr:" + abbr.upper()) if abbr else None)

WH_LIC = "U.S. government work published on whitehouse.gov (public domain under 17 U.S.C. § 105 unless the source notes otherwise)"
def executive(budget_addr):
    ex = node("exec", "us", "branch", "Executive branch", branch="executive", sort=0,
              about="Article II of the U.S. Constitution: the President, the Vice President, the Cabinet, the Executive Office of the President, the 15 executive departments and the independent agencies.",
              source_label="Federal Register agencies API + whitehouse.gov", source_url="https://www.federalregister.gov/agencies")
    wh_addr = None; wh_contact = "https://www.whitehouse.gov/contact/"
    try:
        t = text(get(wh_contact))
        m = re.search(r"(The White House 1600 Pennsylvania Avenue, N\.W\. Washington, D\.C\. 20500)", t); wh_addr = m.group(1) if m else None
    except Exception as e: log(f"wh contact: {e}")
    common = dict(branch="executive", address=wh_addr, contact_form=wh_contact, website="https://www.whitehouse.gov/", photo_credit="The White House (whitehouse.gov)", photo_license=WH_LIC)
    try:
        h = get("https://www.whitehouse.gov/administration/")
        imgs = re.findall(r'<img[^>]*src="(https://www\.whitehouse\.gov/wp-content/uploads/[^"?]+)', h)
        labels = [strip(x) for x in re.findall(r">([^<>]{4,60})<", h)]
        pres = next((l[len("President "):] for l in labels if re.match(r"^President [A-Z]", l)), None)
        vp = next((l[len("Vice President "):] for l in labels if re.match(r"^Vice President [A-Z]", l)), None)
        pimg = next((i for i in imgs if re.search(r"/President-[^/]*Portrait", i)), None)
        vimg = next((i for i in imgs if "/Vice-President" in i), None)
        if pres: node("person:president", ex, "person", pres, title="President of the United States", photo_url=pimg, sort=0, source_label="whitehouse.gov/administration", source_url="https://www.whitehouse.gov/administration/", **common)
        if vp: node("person:vp", ex, "person", vp, title="Vice President of the United States (President of the Senate)", photo_url=vimg, sort=1, source_label="whitehouse.gov/administration", source_url="https://www.whitehouse.gov/administration/", **common)
        src("wh_admin", "The White House: Administration", "https://www.whitehouse.gov/administration/", "U.S. government work", ok=bool(pres and vp), count=int(bool(pres)) + int(bool(vp)))
    except Exception as e: src("wh_admin", "The White House: Administration", "https://www.whitehouse.gov/administration/", "U.S. government work", ok=False, error=str(e)[:200])
    cab = node("exec:cabinet", ex, "group", "The Cabinet", branch="executive", sort=2, about="Cabinet members and Cabinet-level officials as listed by the White House.",
               source_label="whitehouse.gov/administration/cabinet", source_url="https://www.whitehouse.gov/administration/cabinet/")
    try:
        h = get("https://www.whitehouse.gov/administration/cabinet/"); CAB = []
        for m in re.finditer(r'<h2[^>]*>(.*?)</h2>\s*(?:<hr[^>]*>\s*)?<h3[^>]*>(.*?)</h3>(.{0,1500}?)<img[^>]*src="([^"?]+)', h, re.S):
            CAB.append((strip(m.group(1)), strip(m.group(2)), m.group(4)))
        for i, (nm, ti, im) in enumerate(CAB):
            c2 = dict(common); c2.pop("address"); c2.pop("contact_form"); c2.pop("website")
            node("cab:" + slug(nm), cab, "person", nm, title=ti, photo_url=im, source_label="whitehouse.gov/administration/cabinet",
                 source_url="https://www.whitehouse.gov/administration/cabinet/", sort=i + 1, extra={"agency_hint": ti}, **c2)
        src("wh_cabinet", "The White House: The Cabinet", "https://www.whitehouse.gov/administration/cabinet/", "U.S. government work", ok=bool(CAB), count=len(CAB))
    except Exception as e: src("wh_cabinet", "The White House: The Cabinet", "https://www.whitehouse.gov/administration/cabinet/", "U.S. government work", ok=False, error=str(e)[:200])
    fr = gj("https://www.federalregister.gov/api/v1/agencies.json", timeout=60)
    by = {a["id"]: a for a in fr}; top = [a for a in fr if not a.get("parent_id")]
    TT = {}
    try:
        for a in gj("https://api.usaspending.gov/api/v2/references/toptier_agencies/")["results"]: TT[nkey(a["agency_name"])] = a
    except Exception as e: log(f"toptier: {e}")
    def frname(a):
        n = a["name"]; m = re.match(r"^(.*) Department$", n)
        if m: return "Department of " + ("the " if m.group(1) in ("Treasury", "Interior") else "") + m.group(1)
        m = re.match(r"^(.*), (Office|Bureau|Council|Administration|Commission|Agency|Service) of(?: the)?(.*)$", n)
        return n
    def is_current(a): return bool(ug(frname(a), a.get("short_name")) or TT.get(nkey(frname(a))))
    def agency(a, parent, depth, sort, branch="executive"):
        nm = frname(a); u = ug(nm, a.get("short_name")); tt = TT.get(nkey(nm))
        addr = usagov_address(u, budget_addr) if (u and depth == 0) else None
        logo = a.get("logo") if isinstance(a.get("logo"), dict) else None
        nid = node(f"fr:{a['id']}", parent, "agency", nm, title=a.get("short_name") or None, branch=branch, sort=sort,
                   about=(u or {}).get("about") or (a.get("description") or "")[:600] or None,
                   website=(u or {}).get("website") or a.get("agency_url") or None, phone=(u or {}).get("phone"), contact_form=(u or {}).get("contact"), address=addr,
                   photo_url=(logo or {}).get("thumb_url"), photo_credit="Agency seal via the Federal Register" if logo else None,
                   source_label="Federal Register agencies API" + (" + USA.gov A–Z" if u else ""), source_url=a.get("url"),
                   score_key=tt["toptier_code"] if tt and depth == 0 else None, extra={"usagov": (u or {}).get("page"), "fr_id": a["id"]})
        for j, c in enumerate(sorted((by[c] for c in a.get("child_ids") or [] if c in by), key=lambda x: x["name"])): agency(c, nid, depth + 1, j, branch)
        return nid
    eopa = next((a for a in top if a["name"] == "Executive Office of the President"), None)
    eop = node("exec:eop", ex, "group", "Executive Office of the President", branch="executive", sort=3,
               about="White House offices and councils that support the President (Federal Register hierarchy, plus EOP offices the Federal Register lists at top level).",
               source_label="Federal Register agencies API", source_url="https://www.federalregister.gov/agencies/executive-office-of-the-president",
               score_key=(TT.get(nkey("Executive Office of the President")) or {}).get("toptier_code"))
    EOP_TOP = {"Management and Budget Office", "Science and Technology Policy Office", "Council of Economic Advisers", "National Security Council",
               "Trade Representative, Office of United States", "National Drug Control Policy Office", "Environmental Quality Council", "Office of Management and Budget"}
    if eopa:
        for j, c in enumerate(sorted((by[c] for c in eopa["child_ids"] if c in by), key=lambda x: x["name"])): agency(c, eop, 1, j)
    deps = node("exec:depts", ex, "group", "Executive departments (15)", branch="executive", sort=4,
                about="The 15 executive departments whose heads sit in the Cabinet, with the sub-agencies the Federal Register lists under each.",
                source_label="Federal Register agencies API", source_url="https://www.federalregister.gov/agencies")
    ind = node("exec:independent", ex, "group", "Independent agencies & government corporations", branch="executive", sort=5,
               about="Top-level agencies outside the 15 departments that the Federal Register lists and that USA.gov or USAspending.gov still list as current.",
               source_label="Federal Register agencies API × USA.gov × USAspending.gov", source_url="https://www.federalregister.gov/agencies")
    LEGIS = {"Government Accountability Office", "Library of Congress", "Government Publishing Office", "Architect of the Capitol", "Congressional Budget Office", "Copyright Office, Library of Congress", "Congressional Research Service"}
    JUD = {"Judicial Conference of the United States", "Federal Judicial Center", "Administrative Office of United States Courts", "United States Sentencing Commission", "Sentencing Commission, United States"}
    n_dep = n_ind = 0; leg_list = []; jud_list = []
    for a in sorted(top, key=lambda x: x["name"]):
        if a is eopa: continue
        if a["name"].endswith(" Department"): agency(a, deps, 0, n_dep); n_dep += 1
        elif a["name"] in LEGIS: leg_list.append(a)
        elif a["name"] in JUD: jud_list.append(a)
        elif a["name"] in EOP_TOP: agency(a, eop, 0, 100 + n_ind)
        elif is_current(a): agency(a, ind, 0, n_ind); n_ind += 1
    src("fr_agencies", "Federal Register agencies API (agency hierarchy)", "https://www.federalregister.gov/api/v1/agencies.json", "U.S. government work (public domain)", count=len(fr),
        note=f"{n_dep} departments, {n_ind} current independent agencies; historical agencies that USA.gov and USAspending no longer list are left out")
    deps_by = {r["name"].lower(): r["id"] for r in NODES if r["parent"] == deps}
    for r in NODES:
        if r["id"].startswith("cab:") and r["extra"]:
            ti = json.loads(r["extra"]).get("agency_hint", "").lower(); hit = None
            for dn, did in deps_by.items():
                core = dn.replace("department of ", "").replace("the ", "")
                if core and core in ti: hit = did
            if "secretary of war" in ti: hit = deps_by.get("department of defense")
            if "attorney general" in ti: hit = deps_by.get("department of justice")
            r["extra"] = json.dumps({"agency": hit} if hit else {})
    return leg_list, jud_list, agency

# ------------------------------------------------------------------ legislative
def legislative(leg_list, agency):
    lg = node("leg", "us", "branch", "Legislative branch", branch="legislative", sort=1,
              about="Article I of the U.S. Constitution: the Congress (Senate and House of Representatives) and its support agencies.",
              source_label="unitedstates/congress-legislators", source_url="https://github.com/unitedstates/congress-legislators")
    sen = node("leg:senate", lg, "chamber", "U.S. Senate", branch="legislative", website="https://www.senate.gov/", sort=0, about="100 senators, two per state, six-year terms.")
    hou = node("leg:house", lg, "chamber", "U.S. House of Representatives", branch="legislative", website="https://www.house.gov/", sort=1,
               about="435 voting representatives, plus non-voting delegates and the Resident Commissioner of Puerto Rico.")
    url = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
    L = gj(url, timeout=60); n = 0
    for st in sorted({x["terms"][-1]["state"] for x in L}, key=lambda s: STATES.get(s, s)):
        if any(x["terms"][-1]["state"] == st and x["terms"][-1]["type"] == "sen" for x in L): node(f"leg:senate:{st}", sen, "state", STATES.get(st, st), state=st, branch="legislative", sort=0)
        node(f"leg:house:{st}", hou, "state", STATES.get(st, st), state=st, branch="legislative", sort=0)
    for x in L:
        t = x["terms"][-1]; st = t["state"]; bg = x["id"]["bioguide"]
        nm = x["name"].get("official_full") or f'{x["name"]["first"]} {x["name"]["last"]}'
        if t["type"] == "sen":
            par = f"leg:senate:{st}"; srt = 0 if t.get("state_rank") == "senior" else 1
            ti = f"U.S. Senator for {STATES.get(st, st)}" + (f" ({t['state_rank']})" if t.get("state_rank") else "")
        else:
            par = f"leg:house:{st}"; d = t.get("district"); srt = d or 0
            role = "Delegate" if st in ("DC", "GU", "VI", "AS", "MP") else "Resident Commissioner" if st == "PR" else "U.S. Representative"
            ti = f"{role}, {STATES.get(st, st)}" + (f" district {d}" if d else " at-large" if role == "U.S. Representative" else "")
        node(f"bio:{bg}", par, "person", nm, title=ti, branch="legislative", state=st, party=t.get("party"),
             district=str(t.get("district")) if t.get("district") is not None else None, phone=t.get("phone"), address=t.get("address"), website=t.get("url"), contact_form=t.get("contact_form"),
             photo_url=f"https://unitedstates.github.io/images/congress/225x275/{bg}.jpg", photo_credit="Official photo (GPO Member Guide) via the unitedstates/images project",
             photo_license="Public domain (U.S. government work)", source_label="unitedstates/congress-legislators", source_url=f"https://bioguide.congress.gov/search/bio/{bg}",
             sort=srt, extra={"bioguide": bg, "term_start": t.get("start"), "term_end": t.get("end"), "email_note": "Members of Congress publish a web contact form instead of an email address"}); n += 1
    src("congress_legislators", "unitedstates/congress-legislators: legislators-current", url, "CC0 1.0 public domain dedication", count=n)
    src("congress_images", "unitedstates/images: official Member photos (GPO Member Guide)", "https://github.com/unitedstates/images", "Public domain (U.S. government work)")
    sup = node("leg:agencies", lg, "group", "Legislative branch agencies", branch="legislative", sort=2, source_label="Federal Register agencies API × USA.gov", source_url="https://www.federalregister.gov/agencies")
    for i, a in enumerate(leg_list): agency(a, sup, 0, i, "legislative")
    return n

# ------------------------------------------------------------------ judicial
def judicial(jud_list, agency):
    jd = node("jud", "us", "branch", "Judicial branch", branch="judicial", sort=2,
              about="Article III of the U.S. Constitution: the Supreme Court and the lower federal courts created by Congress.",
              source_label="supremecourt.gov + uscourts.gov", source_url="https://www.uscourts.gov/about-federal-courts")
    sc_addr = sc_phone = None
    try:
        t = text(get("https://www.supremecourt.gov/contact/contactus.aspx"))
        m = re.search(r"U\.S\. Mail: (Supreme Court of the United States 1 First Street, NE Washington, DC 20543)", t); sc_addr = m.group(1) if m else None
        m = re.search(r"Telephone: (\d{3}-\d{3}-\d{4})", t); sc_phone = m.group(1) if m else None
    except Exception as e: log(f"scotus contact: {e}")
    sc = node("jud:scotus", jd, "court", "Supreme Court of the United States", branch="judicial", address=sc_addr, phone=sc_phone, website="https://www.supremecourt.gov/",
              source_label="supremecourt.gov contact page", source_url="https://www.supremecourt.gov/contact/contactus.aspx", sort=0)
    h = get("https://www.supremecourt.gov/about/biographies.aspx")
    n = 0; retired = []
    for part in re.split(r'(?=<img title="[^"]+"[^>]*src="justice_pictures)', h)[1:]:
        m = re.match(r'<img title="([^"]+)"[^>]*src="(justice_pictures/[^"]+)"', part)
        if not m: continue
        full = html.unescape(m.group(1))
        if re.search(r"Justice \w+ retired from the Supreme Court", text(part)[:4000]): retired.append(full.split(",")[0]); continue   # page lists retired Justices too
        if "Chief Justice" in full: nm = full.split(", Chief")[0]; ti = "Chief Justice of the United States"
        else: nm = full.rsplit(", Associate Justice", 1)[0]; ti = "Associate Justice of the Supreme Court"
        node("jus:" + slug(nm), sc, "person", nm, title=ti, branch="judicial", address=sc_addr, phone=sc_phone, website="https://www.supremecourt.gov/about/biographies.aspx",
             photo_url="https://www.supremecourt.gov/about/" + urllib.parse.quote(m.group(2)), photo_credit="Collection of the Supreme Court of the United States (supremecourt.gov)",
             photo_license="Official portrait published by the Supreme Court; credit: Collection of the Supreme Court of the United States",
             source_label="supremecourt.gov: Current Members", source_url="https://www.supremecourt.gov/about/biographies.aspx", sort=0 if "Chief" in ti else n + 1,
             extra={"email_note": "The Supreme Court publishes no public email or comment line for the Justices"}); n += 1
    src("scotus", "Supreme Court of the United States: Current Members + contact page", "https://www.supremecourt.gov/about/biographies.aspx", "Official U.S. government source", ok=n > 0, count=n,
        note=("retired Justices on the same page left out: " + ", ".join(retired)) if retired else None)
    lu = "https://www.uscourts.gov/about-federal-courts/court-role-and-structure/court-website-links"
    h = get(lu)
    ca = node("jud:appeals", jd, "group", "U.S. Courts of Appeals (13 circuits)", branch="judicial", sort=1, source_label="uscourts.gov court website links", source_url=lu)
    dc = node("jud:district", jd, "group", "U.S. District Courts", branch="judicial", sort=2, source_label="uscourts.gov court website links", source_url=lu)
    nc = nd = 0; seen = set(); cur_state = None
    for m in re.finditer(r'<h[2-4][^>]*>([^<]{3,40})</h[2-4]>|<a href="(https?://www\.([a-z0-9]+)\.uscourts\.gov/?)"[^>]*>([^<]+)</a>', h):
        if m.group(1):
            s = NAME2ST.get(strip(m.group(1)).lower()); cur_state = s or cur_state; continue
        u, code, label = m.group(2), m.group(3), strip(m.group(4))
        if code in seen: continue
        if re.fullmatch(r"ca(\d+|dc|fc)", code):
            seen.add(code); node(f"court:{code}", ca, "court", f"U.S. Court of Appeals for the {label}", branch="judicial", website=u, source_label="uscourts.gov", source_url=lu, sort=nc); nc += 1
        elif re.fullmatch(r"[a-z]{2}[nmeswc]?d|nmid", code):
            seen.add(code); st = "MP" if code == "nmid" else code[:2].upper()
            if st not in STATES: continue
            pid = f"jud:district:{st}"
            if pid not in SEEN: node(pid, dc, "state", STATES[st], state=st, branch="judicial", sort=0)
            rest = label.replace(STATES[st], "").strip() if label.startswith(STATES[st]) else ""
            nm = f"U.S. District Court for the {rest + ' District' if rest else 'District'} of {STATES[st]}"
            node(f"court:{code}", pid, "court", nm, branch="judicial", state=st, website=u, source_label="uscourts.gov", source_url=lu, sort=nd); nd += 1
    other = node("jud:other", jd, "group", "Judicial branch agencies", branch="judicial", sort=3)
    for i, a in enumerate(jud_list): agency(a, other, 0, i, "judicial")
    src("uscourts_links", "uscourts.gov: Court website links", lu, "U.S. government work", count=nc + nd, note=f"{nc} courts of appeals, {nd} district courts")
    return n

# ------------------------------------------------------------------ states + local
def states_root():
    s = node("states", "us", "branch", "States & territories", branch="state", sort=3,
             about="Governors (National Governors Association) and state legislators (Open States) for the 50 states, DC and the territories where data exists.")
    for st, nm in sorted(STATES.items(), key=lambda x: x[1]): node(f"st:{st}", s, "state", nm, state=st, branch="state", sort=0)
def governors():
    h = get("https://www.nga.org/governors/"); n = 0
    for m in re.finditer(r'<a\s+href="(https://www\.nga\.org/governors/([a-z\-]+)/)"[^>]*>\s*<div class="current-governors__item__image">\s*<img[^>]*src="([^"]+)"[^>]*>.*?<small class="state">([^<]+)</small>\s*([^<]+)<', h, re.S):
        page, sl, img, stn, label = m.groups()
        st = NAME2ST.get(html.unescape(stn).strip().lower())
        if not st: log(f"nga: unknown state {stn}"); continue
        nm = re.sub(r"^Gov\.\s*", "", html.unescape(label).strip())
        addr = phone = web = None
        try:
            hh = get(page, delay=2); t = text(hh)
            a = re.search(r"Contact Information Address (.{5,160}?) Phone ([\d().\-\s]{10,16}\d)", t)
            if a: addr, phone = re.sub(r"\s+Office$", "", a.group(1).strip()), a.group(2).strip()
            else:
                a = re.search(r"Contact Information Address (.{5,160}?) (?:Additional Information|Staff|Phone)", t); addr = a.group(1).strip() if a else None
            w = re.search(r'<a[^>]*href="([^"]+)"[^>]*>\s*Governor(?:&#8217;|&rsquo;|’|\')s Website', hh); web = w.group(1) if w else None
        except Exception as e: log(f"nga {sl}: {e}")
        node(f"gov:{st}", f"st:{st}", "person", nm, title=f"Governor of {STATES[st]}", branch="state", state=st, address=addr, phone=phone, website=web, photo_url=html.unescape(img),
             photo_credit="Official headshot as published by the National Governors Association (nga.org)", photo_license="Shown for identification; rights belong to the source (nga.org / the governor's office)",
             source_label="National Governors Association: Current Governors", source_url=page, sort=0); n += 1
    src("nga", "National Governors Association: Current Governors (+ each governor's contact page)", "https://www.nga.org/governors/", "Public-record facts quoted with a link; photos © source", ok=n > 0, count=n)
    return n
def openstates():
    n = 0; fails = []
    for st in STATES:
        url = f"https://data.openstates.org/people/current/{st.lower()}.csv"
        try: rows = list(csv.DictReader(io.StringIO(get(url, delay=0.5))))
        except Exception: fails.append(st); continue
        if not rows: continue
        leg = node(f"st:{st}:leg", f"st:{st}", "group", f"{STATES[st]} Legislature", state=st, branch="state", sort=1, source_label="Open States", source_url=url)
        for r in rows:
            ch = r.get("current_chamber") or "legislature"; cid = f"st:{st}:{ch}"
            if cid not in SEEN: node(cid, leg, "chamber", {"upper": "Senate (upper chamber)", "lower": "House / Assembly (lower chamber)", "legislature": "Legislature (unicameral)"}.get(ch, ch), state=st, branch="state", sort={"upper": 0, "lower": 1}.get(ch, 2))
            links = [x for x in (r.get("links") or "").split(";") if x.startswith("http")]
            dist = r.get("current_district") or None
            try: srt = int(re.sub(r"\D", "", dist or "")[:6] or 0)
            except Exception: srt = 0
            role = "State Senator" if ch == "upper" else "State Representative" if ch == "lower" else "Legislator"
            node("os:" + r["id"].split("/")[-1], cid, "person", r["name"], title=f"{role}, {STATES[st]}" + (f" district {dist}" if dist else ""), branch="state", state=st,
                 party=r.get("current_party") or None, district=dist, email=r.get("email") or None, phone=r.get("capitol_voice") or r.get("district_voice") or None,
                 address=r.get("capitol_address") or r.get("district_address") or None, website=links[0] if links else None, photo_url=r.get("image") or None,
                 photo_credit="Image URL published by the state legislature, via Open States" if r.get("image") else None,
                 photo_license="Hosted by the state legislature; rights belong to the source" if r.get("image") else None,
                 source_label="Open States (openstates/people)", source_url=url, sort=srt,
                 extra={"district_address": r.get("district_address") or None, "district_phone": r.get("district_voice") or None, "capitol_address": r.get("capitol_address") or None}); n += 1
    src("openstates", "Open States: current state legislators (bulk CSV per state)", "https://data.openstates.org/people/current/", "CC0 1.0 (openstates/people); images hosted by each legislature",
        ok=n > 0, count=n, error=("no file: " + ",".join(fails)) if fails else None)
    return n
def mayors():
    loc = node("local", "us", "branch", "Local: mayors", branch="local", sort=4,
               about="Mayors of U.S. cities with 30,000+ residents from the U.S. Conference of Mayors directory. County, city-council and school-board officials are not covered: there is no clean, keyless nationwide public dataset for them.",
               source_label="U.S. Conference of Mayors: Meet the Mayors", source_url="https://www.usmayors.org/mayors/meet-the-mayors/")
    n = 0; seen = set()
    def cf(enc):
        k = int(enc[:2], 16); return "".join(chr(int(enc[i:i + 2], 16) ^ k) for i in range(2, len(enc), 2))
    for st, stn in sorted(STATES.items(), key=lambda x: x[1]):
        try: h = get("https://www.usmayors.org/mayors/meet-the-mayors/", data={"searchTerm": stn, "submit": "Search"}, delay=10.5)
        except Exception as e: log(f"uscm {st}: {e}"); continue
        for blk in h.split("<ul>")[1:]:
            blk = blk.split("</ul>")[0]
            m = re.search(r"<b>([^<]+)</b><br>([^<]+?),\s*([A-Z]{2})<br>", blk)
            if not m or m.group(3) != st: continue
            nm, city = html.unescape(m.group(1)).strip(), html.unescape(m.group(2)).strip()
            if (city, st) in seen: continue
            seen.add((city, st))
            img = re.search(r'<img[^>]*src="([^"]+)"', blk); pop = re.search(r"Population: ([\d,]+)", blk)
            web = re.search(r"<a href='([^']+)'>Web Site</a>", blk); ph = re.search(r"Phone: <a href='tel:([^']+)'", blk)
            em = re.search(r'data-cfemail="([0-9a-f]+)"', blk); ne = re.search(r"Next Election Date: ([\d/]+)", blk)
            email = None
            if em:
                try: email = cf(em.group(1))
                except Exception: email = None
                if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", email): email = None
            pid = f"local:{st}"
            if pid not in SEEN: node(pid, loc, "state", stn, state=st, branch="local", sort=0)
            p = int(pop.group(1).replace(",", "")) if pop else None
            node(f"mayor:{st}:{slug(city)}", pid, "person", nm, title=f"Mayor of {city}, {st}", branch="local", state=st, phone=ph.group(1) if ph else None, email=email,
                 website=web.group(1) if web else None, photo_url=html.unescape(img.group(1)) if img else None,
                 photo_credit="Photo as published by the U.S. Conference of Mayors" if img else None, photo_license="Rights belong to the source (usmayors.org / the city)" if img else None,
                 source_label="U.S. Conference of Mayors: Meet the Mayors", source_url="https://www.usmayors.org/mayors/meet-the-mayors/", sort=-(p or 0),
                 extra={"city": city, "population": p, "next_election": ne.group(1) if ne else None}); n += 1
    src("uscm", "U.S. Conference of Mayors: Meet the Mayors (cities 30,000+)", "https://www.usmayors.org/mayors/meet-the-mayors/", "Public-record facts quoted with a link; photos © source", ok=n > 0, count=n)
    return n

def check_photos():
    os.makedirs(CACHE, exist_ok=True); cp = os.path.join(CACHE, "photo_status.json")
    try: known = json.load(open(cp))
    except Exception: known = {}
    todo = sorted({r["photo_url"] for r in NODES if r["photo_url"] and r["kind"] == "person" and (r["photo_url"] not in known or time.time() - known[r["photo_url"]][1] > 7 * 86400)})
    def chk(u):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA, "Range": "bytes=0-2047", "Accept": "image/*"})
            with urllib.request.urlopen(req, timeout=12) as r:
                ct = r.headers.get("Content-Type", ""); b = r.read(2048)
                ok = r.status in (200, 206) and (ct.startswith("image/") or b[:3] == b"\xff\xd8\xff" or b[:4] == b"\x89PNG")
                return u, ("ok" if ok else "not an image (" + ct[:30] + ")")
        except urllib.error.HTTPError as e: return u, f"HTTP {e.code}"
        except Exception as e: return u, "unreachable (" + type(e).__name__ + ")"
    with ThreadPoolExecutor(12) as ex:
        for u, s in ex.map(chk, todo): known[u] = [s, time.time()]
    json.dump(known, open(cp, "w"))
    for r in NODES:
        if r["kind"] != "person": continue
        if r["photo_url"]:
            s = known.get(r["photo_url"], ["unchecked"])[0]
            if s == "ok": r["photo_status"] = "ok"
            else:
                r["photo_status"] = "missing"; r["extra"] = json.dumps({**json.loads(r["extra"] or "{}"), "photo_check": s, "photo_tried": r["photo_url"]}); r["photo_url"] = None
        else: r["photo_status"] = "missing"
    log(f"photo check: {len(todo)} checked now, {sum(1 for r in NODES if r['photo_status'] == 'ok')} ok")

# ------------------------------------------------------------------ scoring inputs
# GAO 2025 High-Risk List: areas whose title names one agency -> that agency (USAspending toptier code). Government-wide areas
# (cybersecurity, IT acquisitions, human capital, real property, climate fiscal exposure, etc.) are not charged to any single agency.
GAO_HR_AGENCIES = {
 "Improving the Delivery of Federal Disaster Assistance": ["070"],
 "Acquisition and Program Management for DOE’s National Nuclear Security Administration and Office of Environmental Management": ["089"],
 "DOD Approach to Business Transformation": ["097"], "DOD Business Systems Modernization": ["097"], "DOD Contract Management": ["097"],
 "DOD Financial Management": ["097"], "DOD Weapon Systems Acquisition": ["097"], "Emergency Loans for Small Businesses": ["073"],
 "Enforcement of Tax Laws": ["020"], "HHS Leadership and Coordination of Public Health Emergencies": ["075"],
 "Improving and Modernizing Federal Disability Programs": ["028"], "Management of Federal Oil and Gas Resources": ["014"],
 "Managing Risks and Improving VA Health Care": ["036"], "Medicare Program & Improper Payments": ["075"], "NASA Acquisition Management": ["080"],
 "National Flood Insurance Program": ["070"], "Protecting Public Health through Enhanced Oversight of Medical Products": ["075"],
 "Strengthening Department of Homeland Security IT and Financial Management Functions": ["070"], "Strengthening Management of the Federal Prison System": ["015"],
 "Strengthening Medicaid Program Integrity": ["075"], "Transforming EPA's Process for Assessing and Managing Chemical Risks": ["068"],
 "VA Acquisition Management": ["036"], "Funding the Nation's Surface Transportation System": ["069"], "Unemployment Insurance System": ["1601"]}
GAO_HR_AGENCIES = {k.replace("’", "'"): v for k, v in GAO_HR_AGENCIES.items()}
def gao_highrisk():
    """gao.gov answers automated requests with HTTP 403, so the Internet Archive's copy of the same official page is read.
    The last good copy is kept in logs/gov_cache/gao_hr.html; if archive.org rate-limits (HTTP 429) that copy is used and labelled."""
    url = "https://web.archive.org/web/2026/https://www.gao.gov/high-risk-list"
    os.makedirs(CACHE, exist_ok=True); cp = os.path.join(CACHE, "gao_hr.html"); cpu = cp + ".url"
    final = url; h = None; err = None; stale = False
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"}), timeout=60) as r: h = r.read().decode("utf-8", "replace"); final = r.geturl(); break
        except Exception as e:
            err = e
            if attempt < 3: time.sleep(30 * (attempt + 1))
    if h and "View the 2025 Report" in h:
        open(cp, "w").write(h); open(cpu, "w").write(final)
    elif os.path.exists(cp):
        h = open(cp).read(); final = open(cpu).read().strip() if os.path.exists(cpu) else url; stale = True
        log(f"gao high-risk: live fetch failed ({err}); using the last good archived copy")
    else: raise err or RuntimeError("GAO High-Risk page unavailable")
    t = text(h)
    m = re.search(r"View the 2025 Report Current List (.*?) When was each High Risk area added", t)
    seg = m.group(1) if m else ""
    i = h.find("View the 2025 Report"); j = h.find("When was each High Risk area added", i)
    areas = [strip(x).replace("’", "’") for x in re.findall(r"<a[^>]*>(.*?)</a>", h[i:j], re.S)]
    areas = [a for a in areas if len(a) > 8 and a not in ("Current List", "View the 2025 Report")]
    snap = re.search(r"/web/(\d{14})", final); snap = snap.group(1) if snap else None
    asof = re.search(r"There are (\d+) areas on our High Risk List as of ([A-Z][a-z]+ \d{4})", t)
    reg = re.search(r"Three areas regressed\W+(.*?)\. And", t)
    src("gao_hr", "GAO High-Risk List (2025 update), read from the Internet Archive copy of gao.gov/high-risk-list (gao.gov returns HTTP 403 to automated requests)",
        "https://www.gao.gov/high-risk-list", "U.S. government work (GAO)", ok=len(areas) >= 30, count=len(areas), as_of=asof.group(2) if asof else None,
        note=(f"archived copy captured {snap[:4]}-{snap[4:6]}-{snap[6:8]} {snap[8:10]}:{snap[10:12]} UTC" if snap else "") + (" (re-used: archive.org was unavailable at this check)" if stale else "") + f" · {final}")
    return {"areas": areas, "n_stated": int(asof.group(1)) if asof else None, "as_of": asof.group(2) if asof else None, "regressed_text": reg.group(1) if reg else None, "archive_url": final}
def ig_recs():
    """oversight.gov Open Recommendations (no API or CSV): pages through each 'Agency reviewed' filter, counting every listed open
    recommendation and the report's age bucket. Polite: one request every 1.5 s."""
    base = "https://www.oversight.gov/reports/recommendations"
    h = get(base, delay=1.5)
    total = re.search(r"([\d,]+)\s*Open Recommendations", text(h)); total = int(total.group(1).replace(",", "")) if total else None
    i = h.find('name="agency-reviewe-investigated-rec[]"'); opts = re.findall(r'value="(\d+)"[^>]*>([^<]+)<', h[i:h.find("</select>", i)])
    out = {}
    for val, nm in opts:
        nm = html.unescape(nm).strip(); cnt = {"lt1": 0, "1to5": 0, "gt5": 0}; reports = 0; page = 0
        last = 0
        while page <= min(last, 400):   # items_per_page counts recommendations (50 per page, grouped under their reports)
            q = urllib.parse.urlencode({"agency-reviewe-investigated-rec[]": val, "items_per_page": 50, "page": page})
            try: ph = get(f"{base}?{q}", delay=1.5)
            except Exception as e: log(f"oversight {nm} p{page}: {e}"); cnt = None; break
            pl = [int(x) for x in re.findall(r'href="\?[^"]*?page=(\d+)', ph)]; last = max([last] + pl)   # pager: highest page number
            arts = ph.split('<article class="node node--type-report')[1:]
            n_here = 0
            for a in arts:
                reports += 1
                age = re.search(r'age-of-recs ([a-z0-9\-]+)', a); age = age.group(1) if age else ""
                b = "lt1" if "less-than-1" in age else "gt5" if "more-than-5" in age else "1to5"
                k = a.count("node--type-recommendation"); cnt[b] += k; n_here += k
            if not n_here: break
            page += 1
        if cnt is not None: out[nm] = {"open": sum(cnt.values()), **cnt, "reports": reports}
    src("oversight_recs", "Oversight.gov (CIGIE): Open Recommendations, by agency reviewed", base, "U.S. government work (CIGIE / Offices of Inspector General)",
        ok=bool(out), count=total, note=f"{len(out)} agencies paged; site-wide {total:,} open recommendations" if total else None)
    return out
def ig_vacancies():
    url = "https://www.oversight.gov/about/inspectors-general-vacancies"
    t = text(get(url, delay=1.5))
    seg = t[t.find("Length of Time IG Position Vacant Days OIG") + len("Length of Time IG Position Vacant Days OIG"):t.find("Days Vacant Nominating Authority")]
    out = {nm.strip(): int(d.replace(",", "")) for nm, d in re.findall(r"([A-Z][A-Za-z.,'&\- ]+?) ([\d,]+)(?= |$)", seg)}
    src("ig_vacancies", "Oversight.gov: Inspector General vacancies (days vacant)", url, "U.S. government work (CIGIE)", ok=bool(out), count=len(out))
    return out
def usaspending():
    tt = gj("https://api.usaspending.gov/api/v2/references/toptier_agencies/")["results"]
    n = datetime.now(timezone.utc); fy = n.year if n.month >= 10 else n.year - 1   # latest fiscal year that has ended (FY ends Sep 30)
    try: gj(f"https://api.usaspending.gov/api/v2/reporting/agencies/overview/?fiscal_year={fy}&fiscal_period=12&limit=1")
    except Exception: fy -= 1   # its year-end (period 12) submissions are not published yet -> previous complete year
    big = [a for a in tt if (a.get("budget_authority_amount") or 0) >= 5e8]
    def one(a):
        try:
            d = gj(f"https://api.usaspending.gov/api/v2/agency/{a['toptier_code']}/budgetary_resources/", timeout=40)
            return a["toptier_code"], next((x for x in d["agency_data_by_year"] if x["fiscal_year"] == fy), None)
        except Exception: return a["toptier_code"], None
    br = {}
    with ThreadPoolExecutor(4) as ex:
        for code, y in ex.map(one, big): br[code] = y
    rep = {}; page = 1
    while page < 6:
        d = gj(f"https://api.usaspending.gov/api/v2/reporting/agencies/overview/?fiscal_year={fy}&fiscal_period=12&limit=100&page={page}")
        for x in d["results"]: rep[x["toptier_code"]] = x
        if not d["page_metadata"].get("hasNext"): break
        page += 1
    src("usaspending", f"USAspending.gov API: agency budgetary resources + agency reporting overview (FY{fy}, period 12)", "https://api.usaspending.gov/docs/endpoints",
        "U.S. government work (Treasury)", ok=bool(br), count=len(big), as_of=f"FY{fy}", note="agencies with ≥ $0.5B budget authority")
    return tt, br, rep, fy
def judicial_stats():
    t = text(get("https://www.uscourts.gov/data-news/judicial-vacancies/current-judicial-vacancies"))
    v = re.search(r"Update as of (\d+/\d+/\d{4}) Total Vacancies: (\d+) Total Nominees Pending: (\d+)", t)
    e = re.search(r"Update as of (\d+/\d+/\d{4}) Total Emergencies: (\d+)", text(get("https://www.uscourts.gov/data-news/judicial-vacancies/judicial-emergencies")))
    auth = None
    try:
        import subprocess
        pdf = get("https://www.uscourts.gov/sites/default/files/2025-01/allauth.pdf", raw=True, cache_days=7)
        open("/tmp/bn_allauth.pdf", "wb").write(pdf)
        out = subprocess.run(["pdftotext", "-layout", "/tmp/bn_allauth.pdf", "-"], capture_output=True, text=True).stdout
        rows = [l for l in out.splitlines() if re.match(r"^\s*20\d\d\s", l)]
        if rows: nums = re.findall(r"\d+", re.sub(r",\s*\d+T", "", rows[-1])); auth = {"year": int(nums[0]), "art3": int(nums[-2])}
    except Exception as ex: log(f"allauth: {ex}")
    d = {"as_of": v.group(1) if v else None, "vacancies": int(v.group(2)) if v else None, "nominees": int(v.group(3)) if v else None,
         "emergencies": int(e.group(2)) if e else None, "authorized": auth["art3"] if auth else None, "authorized_year": auth["year"] if auth else None}
    src("uscourts_vac", "uscourts.gov: current judicial vacancies, judicial emergencies, authorized judgeships (allauth.pdf)", "https://www.uscourts.gov/data-news/judicial-vacancies/current-judicial-vacancies",
        "U.S. government work", ok=v is not None, as_of=d["as_of"], note=f"{auth['art3']} authorized Article III judgeships ({auth['year']})" if auth else None)
    return d
def plaw():
    out = {}
    for c in range(113, 120):
        try:
            d = gj(f"https://www.govinfo.gov/bulkdata/json/PLAW/{c}/public", cache_days=0 if c == 119 else 30)
            out[c] = sum(1 for f in d["files"] if re.match(rf"PLAW-{c}publ\d+\.xml$", f["name"]))
        except Exception as e: log(f"plaw {c}: {e}")
    src("govinfo_plaw", "GovInfo bulk data: Public Laws by Congress (113th–119th)", "https://www.govinfo.gov/bulkdata/PLAW", "U.S. government work (GPO)", ok=119 in out, count=out.get(119))
    return out
def house_votes():
    tot = nv = n = 0; last = None
    for yr in (2025, 2026):
        miss = 0; k = 1
        while miss < 3 and k < 2000:
            url = f"https://clerk.house.gov/evs/{yr}/roll{k:03d}.xml"; k += 1
            cpp = os.path.join(CACHE, hashlib.sha1((url + "None").encode()).hexdigest())
            try:
                x = get(url, delay=0.3, cache_days=3650)
                if "<rollcall-vote" not in x: raise ValueError("not a roll call")
            except Exception:
                if os.path.exists(cpp): os.unlink(cpp)
                miss += 1; continue
            miss = 0
            tt = re.search(r"<totals-by-vote>(.*?)</totals-by-vote>", x, re.S)
            if not tt: continue
            vals = {m.group(1): int(m.group(2)) for m in re.finditer(r"<(yea|nay|present|not-voting)-total>(\d+)<", tt.group(1))}
            tot += sum(vals.values()); nv += vals.get("not-voting", 0); n += 1
            d = re.search(r"<action-date>([^<]+)<", x); last = d.group(1) if d else last
    src("house_clerk", "Office of the Clerk, U.S. House: roll call vote XML (119th Congress, 2025–2026)", "https://clerk.house.gov/Votes", "U.S. government work", ok=n > 0, count=n, as_of=last,
        note="Senate roll-call XML (senate.gov) answers automated requests with HTTP 403, so Senate attendance is not scored")
    return {"votes": n, "participation": (1 - nv / tot) if tot else None, "last": last}

# ------------------------------------------------------------------ scoring (blackout.network composite index, 0-100, not an official rating)
WEIGHTS = {"gao_hr": 25, "ig_recs": 25, "data_quality": 20, "ig_vacancy": 15, "budget_exec": 15}
MIN_COMPONENTS = 4   # an agency needs 4 of the 5 inputs (so a missing IG record cannot leave it scored on GAO + spending alone)
def clamp(x): return round(max(0.0, min(100.0, x)), 1)
def build_scores(hr, recs, igv, tt, br, rep, fy, jst, laws, hv):
    tt_by = {a["toptier_code"]: a for a in tt}
    rec_by = {nkey(k): v for k, v in recs.items()}
    igv_by = {nkey(k): (k, v) for k, v in igv.items()}
    hr_by = {}
    for a in hr.get("areas", []):
        a2 = re.sub(r"\s*[–-]\s*NEW$", "", a).strip().replace("’", "'")
        for code in GAO_HR_AGENCIES.get(a2, []): hr_by.setdefault(code, []).append(a2)
    hr_ok = len(hr.get("areas", [])) >= 30
    br_of = {r["score_key"]: r["branch"] for r in NODES if r.get("score_key")}   # e.g. GAO is a legislative-branch agency
    agencies = []
    for code, y in br.items():
        a = tt_by[code]; nm = a["agency_name"]; key = nkey(nm); comps = {}
        if hr_ok:
            areas = hr_by.get(code, [])
            comps["gao_hr"] = {"score": clamp(100 - 20 * len(areas)), "value": f"{len(areas)} agency-specific GAO High-Risk area(s)" + (": " + "; ".join(areas) if areas else ""), "source": "gao_hr", "date": hr.get("as_of")}
        r = rec_by.get(key)
        if r is not None:
            o = r["open"]
            if o: comps["ig_recs"] = {"score": clamp(100 * (1 - ((r["1to5"] + r["gt5"]) / o + r["gt5"] / o) / 2)),
                                      "value": f"{o:,} open IG recommendations: {r['lt1']:,} under 1 year, {r['1to5']:,} 1–5 years, {r['gt5']:,} over 5 years", "source": "oversight_recs", "date": SOURCES.get("oversight_recs", {}).get("fetched")}
            else: comps["ig_recs"] = {"score": 100.0, "value": "0 open IG recommendations listed", "source": "oversight_recs", "date": SOURCES.get("oversight_recs", {}).get("fetched")}
        if igv and r is not None:
            hit = igv_by.get(key)
            comps["ig_vacancy"] = ({"score": clamp(100 - hit[1] / 10), "value": f"Inspector General post vacant {hit[1]:,} days", "source": "ig_vacancies", "date": SOURCES["ig_vacancies"]["fetched"]} if hit else
                                   {"score": 100.0, "value": "Inspector General post not on the vacancy list (filled)", "source": "ig_vacancies", "date": SOURCES["ig_vacancies"]["fetched"]})
        rp = rep.get(code)
        if rp:
            c1 = bool(rp.get("recent_publication_date_certified")); c2 = (rp.get("tas_account_discrepancies_totals") or {}).get("missing_tas_accounts_count") == 0
            c3 = abs(rp.get("obligation_difference") or 0) < 1
            comps["data_quality"] = {"score": clamp(100 * (c1 + c2 + c3) / 3), "source": "usaspending", "date": f"FY{fy} period 12",
                                     "value": f"{c1 + c2 + c3}/3 USAspending checks passed: certified submission {'yes' if c1 else 'no'} · accounts missing from GTAS {'none' if c2 else 'yes'} · File A vs GTAS obligation difference {'$0' if c3 else 'not $0'} (info: {rp.get('unlinked_contract_award_count') or 0:,} unlinked contract and {rp.get('unlinked_assistance_award_count') or 0:,} unlinked assistance awards)"}
        if y and y.get("agency_budgetary_resources"):
            rate = (y.get("agency_total_obligated") or 0) / y["agency_budgetary_resources"]
            comps["budget_exec"] = {"score": clamp(100 * rate), "value": f"{rate * 100:.1f}% of ${y['agency_budgetary_resources'] / 1e9:,.1f}B FY{fy} budgetary resources obligated", "source": "usaspending", "date": f"FY{fy}"}
        w = sum(WEIGHTS[k] for k in comps)
        sc = round(sum(WEIGHTS[k] * c["score"] for k, c in comps.items()) / w, 1) if w and len(comps) >= MIN_COMPONENTS else None
        agencies.append({"code": code, "name": nm, "abbr": a.get("abbreviation"), "branch": br_of.get(code, "executive"), "score": sc, "n_components": len(comps), "weight_covered": w, "components": comps,
                         "budget": y.get("agency_budgetary_resources") if y else None, "missing": [k for k in WEIGHTS if k not in comps]})
    scored = [a for a in agencies if a["score"] is not None and a["branch"] == "executive"]   # Executive score = executive-branch agencies only
    exec_score = round(sum(a["score"] for a in scored) / len(scored), 1) if scored else None
    lc = {}
    if laws.get(119):
        prior = sorted(laws[c] for c in range(113, 119) if c in laws); med = prior[len(prior) // 2] if prior else None
        el = max(1, (date.today() - date(2025, 1, 3)).days); frac = min(1.0, el / 730); pace = laws[119] / frac
        if med: lc["laws"] = {"score": clamp(100 * pace / med), "weight": 50, "source": "govinfo_plaw", "date": SOURCES["govinfo_plaw"]["fetched"], "history": laws,
                              "value": f"{laws[119]} public laws in the 119th Congress after {el} of 730 days → full-term pace {pace:.0f} vs. median {med} for the 113th–118th Congresses"}
    if hv.get("participation") is not None:
        lc["house_attendance"] = {"score": clamp(100 * hv["participation"]), "weight": 50, "source": "house_clerk", "date": hv["last"],
                                  "value": f"House members cast a vote (yea, nay or present) on {hv['participation'] * 100:.1f}% of voting opportunities across {hv['votes']:,} roll calls (2025–2026)"}
    lc["senate_attendance"] = {"score": None, "weight": 0, "source": None, "value": "no data: senate.gov roll-call XML answers automated requests with HTTP 403"}
    lc["appropriations_on_time"] = {"score": None, "weight": 0, "source": None, "value": "no data: no keyless structured source (the Congress.gov API needs a key, and no accounts are created)"}
    jc = {}
    if jst.get("vacancies") is not None and jst.get("authorized"):
        vr = jst["vacancies"] / jst["authorized"]
        jc["vacancy_rate"] = {"score": clamp(100 * (1 - vr / 0.10)), "weight": 40, "source": "uscourts_vac", "date": jst["as_of"],
                              "value": f"{jst['vacancies']} vacancies of {jst['authorized']} authorized Article III judgeships = {vr * 100:.1f}% (0% scores 100, 10% or more scores 0)"}
    if jst.get("emergencies") is not None and jst.get("vacancies"):
        jc["emergencies"] = {"score": clamp(100 * (1 - jst["emergencies"] / jst["vacancies"])), "weight": 30, "source": "uscourts_vac", "date": jst["as_of"],
                             "value": f"{jst['emergencies']} of {jst['vacancies']} vacancies are designated judicial emergencies (caseload-based)"}
    if jst.get("nominees") is not None and jst.get("vacancies"):
        jc["nominees"] = {"score": clamp(100 * jst["nominees"] / jst["vacancies"]), "weight": 30, "source": "uscourts_vac", "date": jst["as_of"],
                          "value": f"{jst['nominees']} of {jst['vacancies']} vacancies have a nominee pending"}
    jc["caseload"] = {"score": None, "weight": 0, "source": None, "value": "not scored: Federal Court Management Statistics are PDF/Excel tables with no stable keyless API"}
    def wavg(d):
        w = sum(c["weight"] for c in d.values() if c["score"] is not None)
        return round(sum(c["score"] * c["weight"] for c in d.values() if c["score"] is not None) / w, 1) if w else None
    br_s = {"executive": exec_score, "legislative": wavg(lc), "judicial": wavg(jc)}
    overall = round(sum(br_s.values()) / 3, 1) if all(v is not None for v in br_s.values()) else None
    return {"overall": overall, "branches": br_s, "computed": now(), "fy": fy,
            "executive": {"agencies": sorted(agencies, key=lambda a: (a["score"] is None, -(a["score"] or 0))), "n_scored": len(scored), "n_total": len(agencies), "weights": WEIGHTS, "min_components": MIN_COMPONENTS},
            "legislative": lc, "judicial": jc, "gao_hr": hr}

# ------------------------------------------------------------------ write
SCHEMA = """CREATE TABLE nodes(id TEXT PRIMARY KEY, parent TEXT, kind TEXT, name TEXT, title TEXT, branch TEXT, state TEXT, party TEXT, district TEXT,
 photo_url TEXT, photo_credit TEXT, photo_license TEXT, photo_status TEXT, email TEXT, phone TEXT, address TEXT, website TEXT, contact_form TEXT,
 about TEXT, source_label TEXT, source_url TEXT, fetched TEXT, sort INTEGER, score_key TEXT, extra TEXT);
CREATE INDEX nodes_parent ON nodes(parent, sort, name); CREATE INDEX nodes_state ON nodes(state, kind);
CREATE VIRTUAL TABLE nodes_fts USING fts5(id UNINDEXED, name, title, place, tokenize='unicode61 remove_diacritics 2');
CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);"""
def write(scores):
    tmp = DB + ".tmp"
    if os.path.exists(tmp): os.unlink(tmp)
    c = sqlite3.connect(tmp); c.executescript(SCHEMA)
    cols = list(NODES[0].keys())
    c.executemany(f"INSERT INTO nodes({','.join(cols)}) VALUES({','.join('?' * len(cols))})", [tuple(r[k] for k in cols) for r in NODES])
    def place(r):
        e = json.loads(r["extra"]) if r["extra"] else {}
        return " ".join(x for x in (r["state"], STATES.get(r["state"] or ""), e.get("city") if isinstance(e, dict) else None) if x)
    c.executemany("INSERT INTO nodes_fts(id,name,title,place) VALUES(?,?,?,?)", [(r["id"], r["name"], " ".join(x for x in (r["title"], r["party"]) if x), place(r)) for r in NODES if r["kind"] != "root"])
    for k, v in (("scores", scores), ("sources", SOURCES), ("updated", now())): c.execute("INSERT INTO meta VALUES(?,?)", (k, json.dumps(v)))
    c.commit(); c.execute("VACUUM"); c.close()
    os.replace(tmp, DB)
def previous(key):
    try:
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); v = c.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone(); c.close()
        return json.loads(v[0]) if v else None
    except Exception: return None
def step(name, fn, *a, default=None):
    t0 = time.time()
    try: r = fn(*a); log(f"{name}: ok in {time.time() - t0:.0f}s"); return r
    except Exception as e: log(f"{name}: FAILED {e}\n{traceback.format_exc()[-900:]}"); return default

def load_nodes():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); c.row_factory = sqlite3.Row
    NODES.clear(); SEEN.clear(); SOURCES.clear()
    for r in c.execute("SELECT * FROM nodes ORDER BY rowid"): NODES.append(dict(r)); SEEN.add(r["id"])
    old = json.loads((c.execute("SELECT v FROM meta WHERE k='sources'").fetchone() or ["{}"])[0]); c.close()
    SOURCES.update(old)
def score_inputs(prev):
    hr = step("gao high-risk", gao_highrisk) or prev.get("gao_hr") or {"areas": []}
    recs = step("ig recs", ig_recs, default={}); igv = step("ig vacancies", ig_vacancies, default={})
    us = step("usaspending", usaspending, default=([], {}, {}, None)); jst = step("courts", judicial_stats, default={})
    laws = step("public laws", plaw, default={}); hv = step("house votes", house_votes, default={})
    return step("scores", build_scores, hr, recs, igv, *us, jst, laws, hv, default=prev)
def rescore():
    """Re-collect only the score inputs and rewrite government.db with the existing org-chart nodes (no org-chart re-crawl)."""
    load_nodes(); log(f"rescore: {len(NODES)} existing nodes")
    scores = score_inputs(previous("scores") or {}); write(scores); log(f"rescore wrote {DB}")

def run(only=None):
    NODES.clear(); SEEN.clear(); SOURCES.clear()
    node("us", None, "root", "United States government", sort=0, about="Federal, state and local officeholders from official public records.")
    step("usa.gov index", usagov_index)
    budget = [int(os.environ.get("BN_GOV_ADDR_BUDGET", "60"))]
    leg_list, jud_list, agency = step("executive", executive, budget, default=([], [], None))
    if agency: step("legislative", legislative, leg_list, agency); step("judicial", judicial, jud_list, agency)
    states_root(); step("governors", governors); step("openstates", openstates); step("mayors", mayors)
    step("photos", check_photos)
    scores = score_inputs(previous("scores") or {})
    if len(NODES) < 2000: raise SystemExit(f"only {len(NODES)} nodes collected; keeping the previous government.db")
    write(scores); log(f"wrote {DB}: {len(NODES)} nodes")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "once"
    if cmd == "once": run()
    elif cmd == "loop":
        while True:   # daily: next run 24 h after the last successful write (so a restart doesn't re-crawl right away)
            age = time.time() - os.path.getmtime(DB) if os.path.exists(DB) else 1e9
            if age < 24 * 3600: time.sleep(min(3600, 24 * 3600 - age)); continue
            try: run()
            except BaseException as e: log(f"run failed: {e}"); time.sleep(3 * 3600)
    elif cmd == "rescore": rescore()
    elif cmd == "status":
        c = sqlite3.connect(DB); print(c.execute("SELECT v FROM meta WHERE k='updated'").fetchone(), c.execute("SELECT kind, count(*) FROM nodes GROUP BY kind").fetchall())
