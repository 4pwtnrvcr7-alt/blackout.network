#!/usr/bin/env python3
"""blackout.network Sources catalog builder.
Builds sources.db: one row per source the monitor has used (blackout.db alerts, opened read-only via file:blackout.db?mode=ro),
plus the scanner's configured feeds (source_health table + sources_ext lists), political_watch.json, youtube_channels.json and
source_candidates.json. Profiles come from sources_profiles.PROFILES (others are marked "pending"); ratings come from rate()
below, a fixed, documented rule. Manual overrides (table `overrides`) and custom profiles (table `profiles_custom`) survive refreshes.
Usage: python3 sources_catalog.py --refresh      (idempotent: rebuilds the derived rows, keeps overrides/queue/candidates)
       python3 sources_catalog.py --override "<name>" 7 "note"   |   --clear-override "<name>"   |   --stats"""
import os, re, sys, json, sqlite3, time, argparse, collections
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
SRC_DB = os.path.join(BASE, "blackout.db")
DB = os.environ.get("SOURCES_DB", os.path.join(BASE, "sources.db"))
SUB_DB = os.environ.get("SOURCE_SUBMISSIONS_DB", os.path.join(BASE, "source_submissions.db"))
CANDIDATES_JSON = os.path.join(BASE, "source_candidates.json")
CATEGORIES = ["war/conflict", "disease", "natural disaster", "cyber", "space weather", "political", "financial"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(key TEXT PRIMARY KEY, name TEXT, type TEXT, link TEXT, link_norm TEXT, family TEXT, n_items INTEGER,
  first_seen TEXT, last_seen TEXT, categories TEXT, top_category TEXT, profile TEXT, profile_status TEXT, rating_auto INTEGER, rating INTEGER,
  rating_reason TEXT, overridden INTEGER DEFAULT 0, origin TEXT, role TEXT, party TEXT, grp TEXT, status TEXT, confirmed_share REAL,
  cited_share REAL, updated TEXT);
CREATE INDEX IF NOT EXISTS ix_src_type ON sources(type);
CREATE INDEX IF NOT EXISTS ix_src_link ON sources(link_norm);
CREATE TABLE IF NOT EXISTS overrides(key TEXT PRIMARY KEY, rating INTEGER, note TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS profiles_custom(key TEXT PRIMARY KEY, profile TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS candidates(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, url_norm TEXT UNIQUE, type TEXT, category TEXT,
  why TEXT, origin TEXT, added TEXT, status TEXT DEFAULT 'under review', submission_id INTEGER);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""

# Public submissions live in a SEPARATE database: sources.db is box-owned (rebuilt here, synced out to the Render copy and overwritten
# there), while source_submissions.db is Render-owned (written by the public form/admin, copied back to the box). Never mix them.
SUB_SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, url_norm TEXT, type TEXT, category TEXT, why TEXT,
  email TEXT, ip_hash TEXT, status TEXT DEFAULT 'pending', created TEXT, reviewed TEXT, review_note TEXT);
CREATE INDEX IF NOT EXISTS ix_sub_url ON submissions(url_norm);
CREATE TABLE IF NOT EXISTS approved_candidates(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, url_norm TEXT UNIQUE, type TEXT, category TEXT,
  why TEXT, origin TEXT, added TEXT, status TEXT DEFAULT 'under review', submission_id INTEGER);
CREATE TABLE IF NOT EXISTS discards(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, reason TEXT, domain TEXT);
CREATE TABLE IF NOT EXISTS attempts(kind TEXT, k TEXT, ts REAL);
CREATE INDEX IF NOT EXISTS ix_att ON attempts(kind, k, ts);
"""

def now_iso(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

_INIT = {}
def db(path=None):
    p = path or DB
    c = sqlite3.connect(p, timeout=15); c.row_factory = sqlite3.Row
    if not _INIT.get(p):
        c.execute("PRAGMA journal_mode=WAL"); c.executescript(SCHEMA); c.commit(); _INIT[p] = True
    return c

def sub_db(path=None):
    p = path or SUB_DB
    c = sqlite3.connect(p, timeout=15); c.row_factory = sqlite3.Row
    if not _INIT.get(p):
        c.execute("PRAGMA journal_mode=WAL"); c.executescript(SUB_SCHEMA); c.commit(); _INIT[p] = True
    return c

def src_db():
    c = sqlite3.connect(f"file:{SRC_DB}?mode=ro", uri=True, timeout=15); c.row_factory = sqlite3.Row
    return c

# ---------------------------------------------------------------- URL normalization (shared with sources.py submissions)
TRACK = re.compile(r"^(utm_.*|fbclid|gclid|mc_cid|mc_eid|ref|ref_src|igshid|si|feature|s|t)$", re.I)
def norm_url(u):
    """-> canonical form used for dedupe, or None if not an http(s) URL with a real host."""
    s = (u or "").strip()
    if not s: return None
    if not re.match(r"^[a-z][a-z0-9+.-]*://", s, re.I): s = "https://" + s
    try: p = urlparse(s)
    except Exception: return None
    if p.scheme.lower() not in ("http", "https"): return None
    host = (p.hostname or "").lower().rstrip(".")
    if not host or "." not in host or " " in host: return None
    try: host = host.encode("idna").decode("ascii")
    except Exception: return None
    for pre in ("www.", "m.", "mobile."):
        if host.startswith(pre) and host.count(".") >= 2: host = host[len(pre):]
    if host in ("twitter.com", "x.com", "mobile.twitter.com"): host = "x.com"
    path = re.sub(r"/{2,}", "/", p.path or "/")
    if host == "t.me" and path.startswith("/s/"): path = path[2:]
    if host in ("x.com", "t.me", "bsky.app", "reddit.com", "youtube.com", "instagram.com", "facebook.com", "tiktok.com"): path = path.lower()
    q = "&".join(kv for kv in (p.query or "").split("&") if kv and not TRACK.match(kv.split("=", 1)[0]))
    path = path.rstrip("/") or ""
    return f"https://{host}{path}" + (f"?{q}" if q else "")

def domain_of(u):
    try:
        h = (urlparse(u if "://" in (u or "") else "https://" + (u or "")).hostname or "").lower()
        return h[4:] if h.startswith("www.") else h
    except Exception: return ""

# ---------------------------------------------------------------- catalog keys, types, links
AGENCY_LINKS = {
 "GDACS": "https://www.gdacs.org/", "NWS (api.weather.gov)": "https://www.weather.gov/", "USGS": "https://earthquake.usgs.gov/earthquakes/",
 "NOAA SWPC": "https://www.swpc.noaa.gov/", "CISA Advisories": "https://www.cisa.gov/news-events/cybersecurity-advisories",
 "CISA KEV": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog", "CIDRAP News": "https://www.cidrap.umn.edu/",
 "NASA EONET": "https://eonet.gsfc.nasa.gov/", "State Dept travel advisories": "https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html",
 "ReliefWeb Updates": "https://reliefweb.int/updates", "SEC press releases": "https://www.sec.gov/newsroom/press-releases",
 "Federal Reserve press": "https://www.federalreserve.gov/newsevents/pressreleases.htm", "tsunami.gov": "https://www.tsunami.gov/",
 "WHO Disease Outbreak News": "https://www.who.int/emergencies/disease-outbreak-news", "X News (trending story summaries)": "https://x.com/explore/tabs/news",
}
AGENCY_NAMES = set(AGENCY_LINKS) - {"CIDRAP News", "X News (trending story summaries)"}
# scanner feed (source_health.name prefix) -> catalog name it produces
HEALTH_MAP = [("GDACS RSS", "GDACS"), ("NWS CAP alerts", "NWS (api.weather.gov)"), ("USGS earthquakes", "USGS"), ("NOAA SWPC", "NOAA SWPC"),
 ("CISA Advisories", "CISA Advisories"), ("CISA KEV", "CISA KEV"), ("CIDRAP News topic", "CIDRAP News"), ("NASA EONET", "NASA EONET"),
 ("State Dept travel", "State Dept travel advisories"), ("ReliefWeb RSS", "ReliefWeb Updates"), ("SEC press", "SEC press releases"),
 ("Federal Reserve press", "Federal Reserve press"), ("tsunami.gov", "tsunami.gov"), ("WHO Disease Outbreak News (API)", "WHO Disease Outbreak News")]
FEED_PROFILES = {   # scanner feeds that produced no items of their own (or are collectors); written from the feed's public purpose
 "AARO news (aaro.mil)": ("Agency feed", 9, "The Pentagon's All-domain Anomaly Resolution Office news page (official UAP reports and statements)."),
 "BEACON": ("Disease surveillance", 7, "BEACON, Boston University's open biothreat early-warning network that publishes curated outbreak reports."),
 "DHS NTAS alerts XML": ("Agency feed", 9, "DHS National Terrorism Advisory System bulletins and alerts (official)."),
 "EpiWatch": ("Disease surveillance", 7, "EpiWatch, an AI-assisted open-source outbreak observatory run by UNSW Sydney researchers."),
 "FDIC failed banks API": ("Agency feed", 10, "FDIC's official list of failed US banks."),
 "ProMED RSS": ("Disease surveillance", 8, "ProMED, the International Society for Infectious Diseases' moderated outbreak reporting list."),
 "US Treasury press release feed": ("Agency feed", 9, "US Treasury press releases, including sanctions (OFAC) actions."),
 "WHO DON legacy RSS": ("Agency feed", 10, "Retired WHO Disease Outbreak News RSS; replaced by the WHO DON API."),
 "ReliefWeb API v1": ("Agency feed", 8, "ReliefWeb's report API (UN OCHA); the RSS feed is used instead."),
 "GDELT DOC 2.0 (artlist + keyword surge timelines)": ("Collector / API", None, "GDELT, a machine-built index of world news coverage; used for article lists and keyword-volume surges, not as a source itself."),
 "Google News RSS search (political, financial, religious, UAP, conflict, disease)": ("Collector / API", None, "Google News search feeds; each article is credited to its publisher in this catalog."),
 "Bluesky public search API": ("Collector / API", None, "Bluesky's public post search; each post is credited to its account in this catalog."),
 "Bluesky public.api.bsky.app": ("Collector / API", None, "Alternate Bluesky search endpoint (disabled)."),
 "Mastodon public hashtag timelines (mastodon.social)": ("Collector / API", None, "Public Mastodon hashtag timelines; each post is credited to its account."),
 "Reddit JSON API": ("Collector / API", None, "Reddit JSON endpoint (blocked, replaced by RSS)."),
 "Discord analyst servers": ("Collector / API", None, "Discord analyst servers (not accessible without login; disabled)."),
 "X (Twitter)": ("Collector / API", None, "Direct X scraping (disabled); X items arrive via the hourly routine's X searches instead."),
 "X/Twitter public search (nitter.net)": ("Collector / API", None, "Nitter mirror search (disabled; mirror unreliable)."),
 "YouTube channel RSS feeds (feeds/videos.xml)": ("Collector / API", None, "YouTube channel RSS. Re-enabled on Oct 31, 2026 through youtube_watch.py; channels are listed individually."),
 "Telegram public previews (t.me/s/: OSINTdefender, ClashReport, warmonitors, intelslava, Middle_East_Spectator, rnintel, BellumActaNews, CIG_telegram, AuroraIntel, insiderpaper, disclosetv, spectatorindex, TheIslanderNews, nexta_live, QudsNen)": ("Collector / API", None, "Public t.me/s/ web previews of the listed Telegram channels; each post is credited to its channel."),
 "Reddit public RSS (multireddit: worldnews, news, geopolitics, CombatFootage, UFOs, UAP, collapse, preppers, economics, wallstreetbets, earthquake, TropicalWeather, OSINT, CredibleDefense, religion, ukraine, Christianity, islam, conspiracy_commons)": ("Collector / API", None, "Reddit's public RSS for the listed communities; each post is credited to its subreddit."),
 "Telegram @WarMonitor3": ("Telegram channel", None, "War Monitor backup channel (preview fetch disabled)."),
 "Telegram @sentdefender, @IntelRepublic": ("Collector / API", None, "Preview fetch for sentdefender and IntelRepublic (disabled)."),
 "YouTube live search (results page, live filter)": ("Collector / API", None, "YouTube live-stream search; each stream is credited to its channel."),
}

def catalog_key(source):
    s = (source or "").strip()
    if re.match(r"^(X (search|news)\b|X News\b|x_news$)", s, re.I): return "X News (trending story summaries)"
    return s

def type_of(name):
    if name in AGENCY_NAMES: return "Agency feed"
    if name == "CIDRAP News": return "Research center"
    if name.startswith("X News"): return "X News summaries"
    for pre, t in (("Google News: ", "News outlet"), ("YouTube LIVE: ", "YouTube channel"), ("YouTube: ", "YouTube channel"), ("X @", "X account"),
                   ("Telegram @", "Telegram channel"), ("Mastodon @", "Mastodon account"), ("Bluesky @", "Bluesky account"), ("Reddit r/", "Reddit community")):
        if name.startswith(pre): return t
    return "Other"

def link_of(name, fam, sample_url):
    if name in AGENCY_LINKS: return AGENCY_LINKS[name]
    m = re.match(r"^X @(\w+)", name)
    if m: return f"https://x.com/{m.group(1)}"
    m = re.match(r"^Telegram @(\w+)", name)
    if m: return f"https://t.me/s/{m.group(1)}"
    m = re.match(r"^Bluesky @(\S+)", name)
    if m: return f"https://bsky.app/profile/{m.group(1)}"
    m = re.match(r"^Reddit (r/\w+)", name)
    if m: return f"https://www.reddit.com/{m.group(1)}/"
    m = re.match(r"^Mastodon @([^@\s]+)@(\S+)$", name)
    if m: return f"https://{m.group(2)}/@{m.group(1)}"
    m = re.match(r"^Mastodon @([^@\s]+)$", name)
    if m:
        h = domain_of(sample_url) or "mastodon.social"
        return f"https://{h}/@{m.group(1)}"
    if name.startswith("Google News: "):
        return f"https://{fam}/" if fam and "." in fam else "https://news.google.com/search?q=" + quote(name[13:])
    if name.startswith("YouTube LIVE: "): return "https://www.youtube.com/results?search_query=" + quote(name[14:])
    return sample_url or ""

# ---------------------------------------------------------------- rating rule (documented on /sources#method)
AGENCY_FAMILIES = {"USGS", "NOAA", "WHO", "GDACS", "CISA", "NASA", "ReliefWeb", "CIDRAP", "StateDept", "SEC", "FederalReserve"}
SOCIAL_TYPES = {"X account", "Telegram channel", "Mastodon account", "Bluesky account", "Reddit community", "YouTube channel", "X News summaries"}
RULE_DOC = [
 ("1 · Starting point", "Official agencies start at 9–10 (10 = primary measurement or declaration such as USGS, NWS, NOAA SWPC, tsunami.gov, WHO, FDIC). "
  "Outlets and accounts in the editorial reliability table (sources_profiles.KNOWN) start at their listed value: wire services 9, major public broadcasters and papers 7–8, "
  "national outlets 6–7, state-run messaging 2–3. Automated relays of agency data start at the agency-relay value (7–8). Otherwise: an unlisted news outlet 5, "
  "an official government account on the political watch list 6, a party, campaign or family account 4, an unlisted social account 3, a Reddit community 2, anything else 1."),
 ("2 · Track record", "For non-agency sources with 5+ stored items: +1 if at least 50% of its items ended up in stories confirmed by 2+ independent source families; "
  "−1 if 10% or fewer did."),
 ("3 · Cites primary sources", "Unlisted social accounts only: +1 if at least 50% of their items link an outlet or agency that is in the reliability table (links to the account's own site or unknown sites don't count)."),
 ("4 · Thin history", "−1 for unlisted sources with fewer than 3 items seen within a single day (too little history to judge)."),
 ("5 · Off-topic", "−1 (non-agency sources with 3+ items) if 40% or more of its items were noise: no threat category, ads or promotions, or trivia the scanner's noise filter ranked 0."),
 ("6 · Bounds and override", "The result is clamped to 0–10, and only official agencies can reach 10. An admin override replaces the computed value and is labelled as such, with its note."),
]
def known_tables():
    import importlib, sources_profiles as P
    importlib.reload(P)
    by_name, by_dom = {}, {}
    for m, kind, v, why in P.KNOWN:
        (by_dom if ("." in m and " " not in m and "@" not in m and ":" not in m) else by_name)[m] = (kind, v, why)
    return P, by_name, by_dom

def rate(rec, by_name, by_dom):
    """-> (rating 0-10 or None, [(label, delta_or_value, why)]). rec: name, type, n, span_h, confirmed, cited, noise, top_family, top_fam_share, origin, grp, verified_type."""
    st = []; name, typ = rec["name"], rec["type"]
    if rec.get("collector"): return None, [("Collector", "n/a", "a collection pipe, not a source; items are rated under the account or outlet that published them")]
    k = by_name.get(name); listed = False; agency = False
    if rec.get("fixed") is not None:
        r = rec["fixed"]; agency = r >= 9; listed = True; st.append(("Start", r, rec["fixed_why"]))
    elif k:
        r = k[1]; agency = k[0] == "agency"; listed = True; st.append(("Start", r, ("official agency: " if agency else "reliability table: ") + k[2]))
    elif typ == "News outlet" and by_dom.get(rec.get("top_family")):
        kk = by_dom[rec["top_family"]]; r = kk[1]; listed = True; st.append(("Start", r, f"reliability table ({rec['top_family']}): {kk[2]}"))
    elif typ in SOCIAL_TYPES and by_dom.get(rec.get("top_family")) and by_dom[rec["top_family"]][0] == "agency" and rec.get("top_fam_share", 0) >= 0.6:
        kk = by_dom[rec["top_family"]]; r = kk[1]; listed = True; st.append(("Start", r, f"automated relay: {kk[2]}"))
    elif rec.get("origin") == "political":
        gov = rec.get("verified_type") == "government" and rec.get("grp") not in ("Party organizations", "Family / close associates", "Campaign figures")
        r = 6 if gov else 4
        st.append(("Start", r, "official government account: authoritative for what the official said, not an independent check of the facts" if gov
                   else "party, campaign or family account: partisan messaging"))
    elif typ == "News outlet": r = 5; st.append(("Start", r, "news outlet not in the reliability table"))
    elif typ == "Reddit community": r = 2; st.append(("Start", r, "user-submitted community; reliability depends on each linked article"))
    elif typ in SOCIAL_TYPES: r = 3; st.append(("Start", r, "social account not in the reliability table"))
    else: r = 1; st.append(("Start", r, "unknown source type"))
    n = rec.get("n", 0)
    if not agency and n >= 5 and rec.get("confirmed") is not None:
        cs = rec["confirmed"]
        if cs >= 0.5: r += 1; st.append(("Track record", "+1", f"{cs:.0%} of {n} items were in stories confirmed by 2+ independent families"))
        elif cs <= 0.10: r -= 1; st.append(("Track record", "−1", f"only {cs:.0%} of {n} items were in independently confirmed stories"))
        else: st.append(("Track record", "0", f"{cs:.0%} of {n} items independently confirmed"))
    if typ in SOCIAL_TYPES and n >= 1 and not listed:
        fams = rec.get("fams") or {}
        good = sum(v for f, v in fams.items() if f in by_dom or f in AGENCY_FAMILIES)
        if good / n >= 0.5: r += 1; st.append(("Cites primary sources", "+1", f"{good / n:.0%} of items link an outlet or agency from the reliability table"))
    if not listed and 0 < n < 3 and rec.get("span_h", 0) < 24: r -= 1; st.append(("Thin history", "−1", f"only {n} item{'s' if n != 1 else ''} seen"))
    if n >= 3 and rec.get("noise", 0) >= 0.4 and not agency: r -= 1; st.append(("Off-topic", "−1", f"{rec['noise']:.0%} of items were noise (no threat category, ads, or trivia ranked 0)"))
    if not agency and r > 9: r = 9; st.append(("Cap", 9, "only official agencies can be rated 10"))
    r = max(0, min(10, int(r)))
    return r, st

# ---------------------------------------------------------------- refresh
def _ld(path, default):
    try: return json.load(open(path))
    except Exception: return default

def gather():
    """Read blackout.db (read-only) + config lists -> dict key -> record."""
    sys.path.insert(0, BASE)
    import scanner as S
    recs = {}
    c = src_db()
    try:
        rows = c.execute("""SELECT a.source, a.family, a.category, a.first_seen, a.last_seen, a.title, a.source_url, a.official, c.eff_families, c.rank AS crank
                            FROM alerts a LEFT JOIN clusters c ON c.cluster_id=a.cluster_id""").fetchall()
        health = [dict(r) for r in c.execute("SELECT * FROM source_health")]
    finally: c.close()
    agg = collections.defaultdict(lambda: {"n": 0, "first": None, "last": None, "cats": collections.Counter(), "fams": collections.Counter(),
                                           "conf": 0, "confn": 0, "cited": 0, "noise": 0, "sample": None, "queries": collections.Counter(), "official": 0})
    for r in rows:
        k = catalog_key(r["source"]); a = agg[k]
        a["n"] += 1
        fs, ls = r["first_seen"], r["last_seen"] or r["first_seen"]
        if fs and (a["first"] is None or fs < a["first"]): a["first"] = fs
        if ls and (a["last"] is None or ls > a["last"]): a["last"] = ls
        a["cats"][r["category"] or "other"] += 1; a["fams"][r["family"] or ""] += 1
        if r["eff_families"] is not None: a["confn"] += 1; a["conf"] += 1 if r["eff_families"] >= 2 else 0
        if (r["family"] or "social") not in ("social",) and not str(r["family"]).startswith("tg:"): a["cited"] += 1
        t = r["title"] or ""
        if (r["category"] == "other" and not r["official"]) or re.search(r"#ad\b|\bdispo\b|promo code|giveaway|premium content|tune in", t, re.I) \
           or (r["crank"] == 0 and not r["official"] and re.search(S.TRIVIA_RX, re.sub(r"\breviewed\b", "", t, flags=re.I), re.I)): a["noise"] += 1
        if not a["sample"]: a["sample"] = r["source_url"]
        if k != r["source"]: a["queries"][r["source"]] += 1
        a["official"] += r["official"] or 0
    for k, a in agg.items():
        fam, fn = (a["fams"].most_common(1) or [("", 0)])[0]
        typ = type_of(k)
        span = 0
        try:
            span = (datetime.fromisoformat(a["last"].replace("Z", "+00:00")) - datetime.fromisoformat(a["first"].replace("Z", "+00:00"))).total_seconds() / 3600
        except Exception: pass
        cats = {x: n for x, n in a["cats"].most_common() if x != "other"} or dict(a["cats"])
        recs[k] = dict(key=k, name=k, type=typ, family=fam, top_family=fam, top_fam_share=fn / a["n"], n=a["n"], first=a["first"], last=a["last"],
                       cats=cats, confirmed=(a["conf"] / a["confn"]) if a["confn"] else None, cited=a["cited"] / a["n"], noise=a["noise"] / a["n"],
                       span_h=span, fams=dict(a["fams"]), link=link_of(k, fam, a["sample"]), origin="blackout.db", status="active", queries=dict(a["queries"].most_common(12)))
    # configured scanner feeds
    for h in health:
        tgt = next((t for p, t in HEALTH_MAP if h["name"].startswith(p)), None)
        st = {1: "ok", 0: "failing", -1: "disabled"}.get(h["ok"], str(h["ok"]))
        if tgt:
            if tgt in recs: recs[tgt]["feed"] = {"name": h["name"], "url": h["url"], "status": st}
            else:
                recs[tgt] = dict(key=tgt, name=tgt, type=type_of(tgt), n=0, link=AGENCY_LINKS.get(tgt, h["url"]), origin="scanner config", status=st, cats={},
                                 feed={"name": h["name"], "url": h["url"], "status": st})
            continue
        m = re.match(r"^Telegram (@[\w, @]+)$", h["name"]) or re.match(r"^Telegram public previews \(t\.me/s/: (.*)\)$", h["name"])
        if m:
            for hd in re.findall(r"@?(\w+)", m.group(1)):
                key = f"Telegram @{hd}"
                if key not in recs:
                    recs[key] = dict(key=key, name=key, type="Telegram channel", n=0, link=f"https://t.me/s/{hd}", origin="scanner config",
                                     status=st if h["name"].startswith("Telegram @") else "configured, no items yet", cats={})
            if not h["name"].startswith("Telegram public previews"): continue
        if h["name"].startswith("Reddit public RSS"):
            for sub in re.findall(r"(\w+)(?:,|\))", h["name"].split("multireddit:", 1)[-1]):
                key = f"Reddit r/{sub}"
                if key not in recs: recs[key] = dict(key=key, name=key, type="Reddit community", n=0, link=f"https://www.reddit.com/r/{sub}/", origin="scanner config", status="configured, no items yet", cats={})
        typ, fixed, prof = FEED_PROFILES.get(h["name"], ("Collector / API", None, None))
        key = "Feed: " + h["name"]
        recs[key] = dict(key=key, name=h["name"], type=typ, n=int(h["items"] or 0) if typ == "Collector / API" else 0, link=h["url"], origin="scanner config",
                         status=st, cats={}, collector=(typ == "Collector / API"), fixed=fixed, fixed_why=("official agency feed" if (fixed or 0) >= 9 else "disease-surveillance network (expert-moderated)") if fixed else None,
                         feed_profile=prof, note=(h.get("note") or h.get("error") or "")[:200])
    # political watch list
    pw = _ld(os.path.join(BASE, "political_watch.json"), {}).get("accounts", [])
    for p in pw:
        key = f"X @{p['handle']}"
        r = recs.get(key) or dict(key=key, name=key, type="X account", n=0, link=p["url"], cats={"political": 0}, status="watch list (read-only)")
        r.update(origin="political", role=p["role"], party=p["party"], grp=p["group"], verified_type=p.get("verified_type"), display=p["name"])
        r.setdefault("cats", {}); r["cats"] = r["cats"] or {"political": 0}
        if "political" not in r["cats"]: r["cats"]["political"] = 0
        recs[key] = r
    # YouTube channel watch
    for ch in _ld(os.path.join(BASE, "youtube_channels.json"), {}).get("channels", []):
        key = f"YouTube: {ch['name']}"
        r = recs.get(key) or dict(key=key, name=key, type="YouTube channel", n=0, cats={}, status="watched (RSS)")
        r.update(link=ch["url"], origin=r.get("origin") if r.get("n") else "youtube watch", yt_kind=ch.get("kind"), status="watched (RSS)")
        recs[key] = r
    # Intel Streams sources (intel_streams.py: Research, Leaks, Patents, M&A, Markets). Each record carries 'fixed' (editorial start rating 0-10),
    # 'grade_key' and 'grade_seed' so the visitor-rating grade system can pick them up by key. Informational only: never affect threat scores.
    try:
        import importlib, intel_streams as IS
        for r in importlib.reload(IS).catalog_records(): recs.setdefault(r["key"], r)
    except Exception as ex: print("sources_catalog: intel streams skipped:", ex)
    return recs

YT_KIND = {"wire service": "a global wire service", "public broadcaster": "a public broadcaster", "international broadcaster": "an international broadcaster",
           "broadcaster": "a broadcaster", "agency": "an official agency", "analysis": "an analysis organization", "OSINT / analysis": "an independent analysis channel",
           "weather": "a severe-weather channel", "space weather": "a space-weather forecasting channel"}

def refresh(path=None, quiet=False):
    P, by_name, by_dom = known_tables()
    recs = gather()
    k = db(path)
    try:
        ov = {r["key"]: dict(r) for r in k.execute("SELECT * FROM overrides")}
        cp = {r["key"]: r["profile"] for r in k.execute("SELECT * FROM profiles_custom")}
        out = []
        ts = now_iso()
        for key, r in recs.items():
            rating, steps = rate(r, by_name, by_dom)
            o = ov.get(key)
            final = rating; over = 0
            if o and o["rating"] is not None:
                final = int(o["rating"]); over = 1
                steps = steps + [("Admin override", final, o["note"] or "set by admin")]
            prof, pst = cp.get(key), "custom" if key in cp else None
            if not prof and key in P.PROFILES: prof, pst = P.PROFILES[key], "written"
            if not prof and r.get("feed_profile"): prof, pst = r["feed_profile"], "written"
            if not prof and r.get("origin") == "political":
                prof = (f"{r.get('display')}: {r.get('role')} ({r.get('party')}). Public X account on the read-only political watch list, used to track official "
                        "statements and exchanges between the parties ahead of the elections. Statements are reported as claims, not verified facts.")
                pst = "written"
            if not prof and key.startswith("YouTube: ") and r.get("yt_kind"):
                prof = (f"Official YouTube channel of {key[9:]}, {YT_KIND.get(r['yt_kind'], r['yt_kind'])}. Polled through its public RSS feed by youtube_watch.py; "
                        "new threat-relevant videos from the last 24 hours go through normal scoring.")
                pst = "written"
            if not prof and key == "X News (trending story summaries)": prof, pst = P.PROFILES.get(key), "written"
            if r.get("queries") and key.startswith("X News"):
                prof = (prof or "") + " Queries used: " + ", ".join(list(r["queries"])[:8]) + "."
            cats = r.get("cats") or {}
            top = next(iter(cats), None)
            feed = r.get("feed") or {}
            out.append((key, r.get("display") and f"{r['display']} ({key})" or r["name"], r["type"], r.get("link") or "", norm_url(r.get("link") or "") or "", r.get("family"), int(r.get("n") or 0),
                        r.get("first"), r.get("last"), json.dumps(cats), top, prof, pst or "pending", rating, final, json.dumps(steps), over, r.get("origin"),
                        r.get("role"), r.get("party"), r.get("grp"), (r.get("status") or "") + (f" · feed {feed['status']}" if feed else "") + (f" · {r['note']}" if r.get("note") else ""),
                        r.get("confirmed"), r.get("cited"), ts))
        k.execute("BEGIN")
        k.execute("DELETE FROM sources")
        k.executemany("INSERT INTO sources VALUES(" + ",".join("?" * 25) + ")", out)
        # candidates from the hourly routine's list (source_candidates.json): list of {name,url,type,category,why,found_at}
        cj = _ld(CANDIDATES_JSON, [])
        if isinstance(cj, dict): cj = cj.get("candidates", [])
        nc = 0
        for cnd in cj if isinstance(cj, list) else []:
            un = norm_url(cnd.get("url") or "")
            if not un or not cnd.get("name"): continue
            nc += k.execute("""INSERT OR IGNORE INTO candidates(name,url,url_norm,type,category,why,origin,added) VALUES(?,?,?,?,?,?,?,?)""",
                            (str(cnd["name"])[:120], cnd["url"][:500], un, str(cnd.get("type") or "")[:40], str(cnd.get("category") or "")[:40],
                             str(cnd.get("why") or cnd.get("note") or "")[:1000], "hourly routine", cnd.get("found_at") or ts)).rowcount
        k.execute("INSERT OR REPLACE INTO meta VALUES('refreshed', ?)", (ts,))
        k.execute("INSERT OR REPLACE INTO meta VALUES('counts', ?)", (json.dumps({"sources": len(out), "with_profile": sum(1 for o in out if o[12] != "pending")}),))
        k.commit()
        res = {"ok": True, "sources": len(out), "profiles": sum(1 for o in out if o[12] != "pending"), "overrides": len(ov), "candidates_imported": nc, "refreshed": ts}
        if not quiet: print(json.dumps(res))
        return res
    finally: k.close()

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true"); ap.add_argument("--stats", action="store_true")
    ap.add_argument("--override", nargs=3, metavar=("NAME", "RATING", "NOTE")); ap.add_argument("--clear-override", metavar="NAME")
    a = ap.parse_args(argv)
    if a.override:
        n, r, note = a.override; r = int(r); assert 0 <= r <= 10
        k = db(); k.execute("INSERT OR REPLACE INTO overrides VALUES(?,?,?,?)", (n, r, note[:300], now_iso())); k.commit(); k.close(); refresh(); return 0
    if a.clear_override:
        k = db(); k.execute("DELETE FROM overrides WHERE key=?", (a.clear_override,)); k.commit(); k.close(); refresh(); return 0
    if a.refresh: refresh(); return 0
    if a.stats:
        k = db()
        for r in k.execute("SELECT type, COUNT(*), SUM(n_items), ROUND(AVG(rating),1) FROM sources GROUP BY type ORDER BY 2 DESC"): print(tuple(r))
        k.close(); return 0
    ap.print_help(); return 0

if __name__ == "__main__":
    sys.exit(main())
