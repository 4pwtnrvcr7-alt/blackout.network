#!/usr/bin/env python3
"""Blackout Network early-warning scanner.
Pulls public machine-readable sources, normalizes, clusters (fuzzy cross-source),
scores severity 0-100, separates watchlist, writes SQLite. Research only."""
import json, os, re, sqlite3, time, math, html, hashlib, traceback, threading
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import requests

BASE = "/workspace/blackout"
DB = f"{BASE}/blackout.db"
UA = {"User-Agent": "Mozilla/5.0 (BlackoutNetwork early-warning research monitor)"}
HIGH = 60            # severity threshold for "high"
WINDOW_H = 12        # dedupe/cluster window
HISTORY_D = 7
SCAN_LOCK = threading.Lock()

def scope_cfg():
    """Scan scope from config.json. scope "global" (default) = worldwide, no local bias; local_boost multiplies the
    optional local-area NWS boost (BN_LOCAL_AREA_RE env var; unset = off): 0 = none, 1 = legacy (+10 score, +1 rank)."""
    try: c = json.load(open(f"{BASE}/config.json"))
    except Exception: c = {}
    scope = str(c.get("scope") or "global").lower()
    try: lb = float(c.get("local_boost", 0 if scope == "global" else 1))
    except Exception: lb = 0.0
    return scope, max(0.0, lb)

def now(): return datetime.now(timezone.utc)
def iso(d): return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None
def parse_t(s):
    if not s: return None
    s = str(s).strip()
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}", s):
            s2 = s.replace("Z", "+00:00").replace(" ", "T", 1)
            d = datetime.fromisoformat(s2)
        else:
            try: d = parsedate_to_datetime(s)
            except Exception: d = datetime.strptime(s, "%a, %d %b %Y")
        if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None
def strip(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()
def get(url, **kw):
    h = {**UA, **kw.pop("headers", {})}
    to = kw.pop("timeout", 30)
    try:
        r = requests.get(url, headers=h, timeout=to, **kw)
    except (requests.ConnectionError, requests.Timeout):
        time.sleep(3); r = requests.get(url, headers=h, timeout=to, **kw)   # one retry on transient network/TLS errors
    r.raise_for_status(); return r

def local(tag): return tag.split("}", 1)[-1]
def rss_items(text):
    raw = text.encode() if isinstance(text, str) else text
    if raw.startswith(b"\xef\xbb\xbf"): raw = raw[3:]
    root = ET.fromstring(raw)
    out = []
    for el in root.iter():
        if local(el.tag) in ("item", "entry"):
            d = {}
            for c in el.iter():
                if c is el: continue
                k = local(c.tag)
                if k == "link" and c.get("href"):
                    d.setdefault("link", c.get("href"))
                else:
                    v = (c.text or "") if len(c) == 0 else "".join(c.itertext())
                    d.setdefault(k, v.strip())
                    for a, av in c.attrib.items(): d.setdefault(f"{k}@{local(a)}", av)
            out.append(d)
    return out

KW = {
 "ufo/uap": r"\b(ufo|ufos|uap|uaps|aaro|extraterrestrial|non-human intelligence|unidentified anomalous|unidentified flying|flying saucer|alien craft)",
 "financial": r"\b(bank failure|bank run|failed bank|circuit breaker|trading halt|trading suspended|currency crisis|currency collapse|devaluation|sovereign default|debt default|defaults on|emergency rate|rate cut|central bank|liquidity facility|bailout|market crash|stock crash|plunge|fdic|bond yields? spike|hyperinflation)",
 "spiritual/religious": r"\b(pope|vatican|mosque|church|cathedral|synagogue|temple|pilgrim|hajj|kumbh|sectarian|religious|blasphemy|clergy|imam|rabbi|apparition|miracle)",
 "political": r"\b(coup|martial law|assassinat|sanction|state of emergency|emergency declaration|declares emergency|impeach|mass protest|protesters|riot|unrest|curfew|election (crisis|fraud|annulled|contested|results)|parliament dissolved|ousted|resign)",
 "war/conflict": r"\b(missile|airstrike|air strike|strike[sd]?|drone|shelling|explosion|invasion|troops|military|artillery|attack|killed|ceasefire|war|nuclear|idf|hamas|hezbollah|houthi|rocket|gunfire|clash|offensive|bomb)",
 "disease": r"\b(outbreak|virus|ebola|marburg|cholera|measles|influenza|h5n1|avian|mpox|dengue|plague|pathogen|epidemic|pandemic|disease|infection|cases)",
 "natural disaster": r"\b(earthquake|tsunami|flood|cyclone|hurricane|typhoon|storm|wildfire|volcan|eruption|landslide|drought|tornado)",
 "cyber": r"\b(cve-|ransomware|vulnerab|exploit|malware|cyber|hack|breach|ddos)",
 "space weather": r"\b(geomagnetic|solar flare|cme|radiation storm|kp index)",
}
NEW_CATS = ("ufo/uap", "financial", "spiritual/religious", "political")
# strong crisis phrasing only (generic words like "explosion"/"outbreak" do not boost; they are usually local incidents)
BOOST_RX = (r"\b(military coup|coup attempt|attempted coup|stages? (a )?coup|declares? martial law|martial law (is )?declared|imposes? martial law|"
            r"assassinated|assassination attempt|declares? (a )?(national )?state of emergency|nationwide (curfew|state of emergency)|"
            r"bank failure|bank run|banks? (collapse|collapses|collapsed)|market-wide circuit breaker|trading halted (on|across) (the )?(nyse|nasdaq|exchange)|"
            r"sovereign default|defaults on (its )?(sovereign|government) debt|currency (collapse|crisis)|emergency rate (cut|hike)|"
            r"sectarian (violence|clashes)|stampede|mass casualt|massacre|nuclear (strike|attack|test|detonation)|ballistic missile|invasion of|"
            r"mystery illness|unknown disease|novel (virus|pathogen)|tsunami warning)")
# ---- 0-10 rank helpers (see README "Severity rank")
THREAT_RX = (r"\b(killed|dead|deaths?|casualt|injured|wounded|evacuat|missile|airstrike|strike|attack|shelling|drone|troops|invasion|war|"
             r"explosion|blast|outbreak|cases|epidemic|virus|infect|protest|riot|clashes|unrest|curfew|sanction|emergency|martial|coup|"
             r"default|collapse|crash|halt|bank|currency|inflation|quake|earthquake|tsunami|flood|cyclone|hurricane|typhoon|wildfire|eruption|"
             r"ransomware|hack|breach|outage|cyber|uap|ufo|aaro|disclosure|sectarian|stampede|massacre|terror|hostage|shooting|gunman|nuclear)")
TRIVIA_RX = (r"\b(halloween|trick.or.treat|festival|parade|fantasy|recipe|season|game|match|playoff|tips|what to know|ranks|ranked|"
             r"school board|city council|town council|county commission|fundraiser|anniversary|celebrat|museum|tourist|home for|"
             r"review|podcast|webinar|movie|film|series|episode|album|concert|horoscope|obituary|wedding|sale|deal|price of|"
             r"nba|nfl|mlb|nhl|points? in|touchdown|quarterback|coach|warriors win|price target|analyst|shares (rise|fall|jump|slide)|earnings|"
             r"stock pick|plane spotting|rail fanning|bigfoot|cryptid|dogman|abduction odds|ufo-shaped|pinned a (photo|message)|follow us|"
             r"subscribe to|join (us|our)|vote!)")
PAST_RX = (r"\b(trial|sentenc|verdict|court|prosecut|special counsel|indict|convicted|appeal|anniversary|years? ago|decades? ago|"
           r"documentary|history of|remember|retrospective|seeks death penalty)")
HIGH_CONSEQ = r"ebola|marburg|bundibugyo|nipah|h5n1|avian|mers|plague|novel (virus|pathogen|coronavirus)|smallpox|mystery illness|unknown disease"
def classify(text, default="other"):
    t = (text or "").lower()
    for cat, rx in KW.items():
        if re.search(rx, t): return cat
    return default

def item(source, family, nid, title, category, url, etime, lat=None, lon=None, location=None,
         base=10, official=True, extra=None):
    return dict(id=hashlib.sha1(f"{source}|{nid}".encode()).hexdigest()[:16], source=source, family=family,
                title=(title or "")[:400], category=category, source_url=url, event_time=iso(etime) if etime else None,
                lat=lat, lon=lon, location=location, base=max(0, min(100, int(base))), official=1 if official else 0,
                extra=json.dumps(extra or {}))

# ---------------------------------------------------------------- fetchers
def f_usgs():
    out = []
    for feed in ("significant_day", "4.5_day"):
        j = get(f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{feed}.geojson").json()
        for f in j["features"]:
            p = f["properties"]; lon, lat, depth = f["geometry"]["coordinates"]
            m = p.get("mag") or 0
            base = 20 + max(0, (m - 4.5)) * 18
            base += {"green": 0, "yellow": 10, "orange": 20, "red": 30}.get(p.get("alert") or "", 0)
            if p.get("tsunami"): base += 10
            out.append(item("USGS", "USGS", f["id"], p.get("title"), "natural disaster", p.get("url"),
                            datetime.fromtimestamp(p["time"] / 1000, timezone.utc), lat, lon, p.get("place"),
                            base, extra={"mag": m, "depth_km": depth, "pager": p.get("alert"), "tsunami": p.get("tsunami"), "felt": p.get("felt")}))
    return out

def centroid(geom):
    try:
        pts = []
        def walk(c):
            if isinstance(c[0], (int, float)): pts.append(c)
            else:
                for x in c: walk(x)
        walk(geom["coordinates"])
        return sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)
    except Exception:
        return None, None

def f_nws():
    j = get("https://api.weather.gov/alerts/active?severity=Extreme,Severe",
            headers={**UA, "Accept": "application/geo+json"}).json()
    out = []
    for f in j["features"]:
        p = f["properties"]
        lat, lon = centroid(f["geometry"]) if f.get("geometry") else (None, None)
        base = {"Extreme": 55, "Severe": 35}.get(p.get("severity"), 20)
        if p.get("urgency") == "Immediate": base += 10
        if p.get("certainty") == "Observed": base += 5
        zones = len((p.get("geocode") or {}).get("UGC") or [])
        base += min(10, zones // 5)
        area = p.get("areaDesc") or ""
        local_fl = bool(os.environ.get("BN_LOCAL_AREA_RE")) and bool(re.search(os.environ["BN_LOCAL_AREA_RE"], area))
        if local_fl: base += round(10 * scope_cfg()[1])   # local-area boost, config-driven (local_boost; 0 in global scope)
        out.append(item("NWS (api.weather.gov)", "NOAA", p["id"], p.get("headline") or p.get("event"),
                        "natural disaster", p.get("@id") or p["id"], parse_t(p.get("onset") or p.get("sent")),
                        lat, lon, area[:200], base,
                        extra={"event": p.get("event"), "severity": p.get("severity"), "urgency": p.get("urgency"),
                               "certainty": p.get("certainty"), "sender": p.get("senderName"), "expires": p.get("expires"), "near_local": local_fl}))
    return out

def f_tsunami():
    out = []
    for code in ("PAAQ", "PHEB"):
        url = f"https://www.tsunami.gov/events/xml/{code}Atom.xml"
        txt = get(url).text
        feed_title = re.search(r"<title>(.*?)</title>", txt)
        ft = strip(feed_title.group(1)) if feed_title else "Tsunami message"
        for e in rss_items(txt):
            s = e.get("summary", "")
            cat = re.search(r"Category:\s*(\w+)", s); mag = re.search(r"Magnitude:\s*([\d.]+)", s)
            c = (cat.group(1) if cat else "").lower()
            base = {"warning": 85, "advisory": 60, "watch": 55, "threat": 70, "information": 20}.get(c, 25)
            lat = float(e["lat"]) if e.get("lat") else None; lon = float(e["long"]) if e.get("long") else None
            out.append(item("tsunami.gov", "NOAA", f"{code}|{e.get('id')}", f"{ft} ({c or 'n/a'}): {e.get('title')}",
                            "natural disaster", e.get("link") or url, parse_t(e.get("updated")), lat, lon, e.get("title"), base,
                            extra={"tsunami_category": c, "mag": float(mag.group(1)) if mag else None, "center": code}))
    return out

def f_swpc():
    out = []
    for a in get("https://services.swpc.noaa.gov/products/alerts.json").json():
        msg = a.get("message", "")
        t = parse_t(a.get("issue_datetime").replace(" ", "T") + "Z") if a.get("issue_datetime") else None
        if t and t < now() - timedelta(days=HISTORY_D): continue
        first = [l.strip() for l in msg.splitlines() if re.match(r"^(ALERT|WARNING|WATCH|SUMMARY|EXTENDED WARNING|CANCEL)", l.strip())]
        head = first[0] if first else msg.splitlines()[0]
        lvls = [int(x) for x in re.findall(r"\b[GSR]([1-5])\b", head)]
        lvl = max(lvls) if lvls else 0
        base = 10 + lvl * 15
        if head.startswith("WATCH"): base -= 5
        out.append(item("NOAA SWPC", "NOAA", f"{a.get('product_id')}|{a.get('issue_datetime')}", "Space weather: " + head[:200],
                        "space weather", "https://www.swpc.noaa.gov/products/alerts-watches-and-warnings", t, None, None,
                        "Global (Earth)", base, extra={"scale_level": lvl, "product_id": a.get("product_id")}))
    k = get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json").json()
    if k:
        last = k[-1] if isinstance(k[-1], dict) else dict(zip(k[0], k[-1]))
        kp = float(last.get("Kp") or last.get("kp_index") or 0)
        if kp >= 5:
            g = int(min(5, kp - 4))
            out.append(item("NOAA SWPC Kp", "NOAA", f"kp|{last.get('time_tag')}", f"Planetary Kp index {kp} (G{g} storm level)",
                            "space weather", "https://www.swpc.noaa.gov/products/planetary-k-index", parse_t(last.get("time_tag")),
                            None, None, "Global (Earth)", 15 + g * 15, extra={"kp": kp}))
    return out, {"latest_kp": (k[-1] if k else None)}

def f_who():
    j = get("https://www.who.int/api/news/diseaseoutbreaknews?$orderby=PublicationDate%20desc&$top=20").json()
    out = []
    for v in j["value"]:
        t = parse_t(v.get("PublicationDate"))
        if t and t < now() - timedelta(days=HISTORY_D): continue
        title = v.get("OverrideTitle") or v.get("Title")
        base = 45
        if re.search(r"ebola|marburg|bundibugyo|novel|h5n1|avian|mers|plague|nipah|pandemic|lassa|sars", title, re.I): base += 20
        countries = re.split(r",| and | - ", title.split(",", 1)[-1]) if "," in title or " - " in title else []
        if len(countries) >= 2: base += 10   # multi-country spread
        out.append(item("WHO Disease Outbreak News", "WHO", v.get("Id"), title, "disease",
                        "https://www.who.int/emergencies/disease-outbreak-news/item/" + (v.get("UrlName") or ""), t,
                        location=(title.split(" - ", 1)[-1].strip() if " - " in title else (title.split(",", 1)[-1].strip() if "," in title else None)), base=base,
                        extra={"summary": strip(v.get("Summary"))[:500], "don_id": v.get("DonId")}))
    return out

def rss_generic(src, fam, url, default_cat, base, official, maxage_d=HISTORY_D, force_cat=False, kwboost=None):
    out = []
    for e in rss_items(get(url).content):
        t = parse_t(e.get("pubDate") or e.get("updated") or e.get("published") or e.get("date"))
        if t and t < now() - timedelta(days=maxage_d): continue
        title = strip(e.get("title")); desc = strip(e.get("description") or e.get("summary"))
        cat = default_cat if force_cat else classify(title + " " + desc, default_cat)
        b = base
        if kwboost and re.search(kwboost, title, re.I): b += 20
        out.append(item(src, fam, e.get("guid") or e.get("id") or e.get("link") or title, title, cat, e.get("link") or url, t,
                        base=b, official=official, extra={"desc": desc[:400]}))
    return out

CIDRAP_TOPICS = {"Ebola": 64, "Avian Influenza": 49, "Marburg": 77, "Measles": 78, "Mpox": 230556, "Nipah": 232665,
                 "Cholera": 58, "Misc Emerging Topics": 31175, "Pandemic Influenza": 86}
def f_cidrap():
    # CIDRAP's site-wide /rss.xml is stale (last item 2022); topic feeds are current.
    out, seen = [], set()
    for name, tid in CIDRAP_TOPICS.items():
        for it in rss_generic("CIDRAP News", "CIDRAP", f"https://www.cidrap.umn.edu/news/{tid}/rss", "disease", 20, True, force_cat=True,
                              kwboost=r"ebola|marburg|bundibugyo|h5n1|avian flu|outbreak|novel|pandemic|nipah|mpox"):
            if it["id"] not in seen: seen.add(it["id"]); out.append(it)
    return out

def f_gdacs():
    out = []
    for e in rss_items(get("https://www.gdacs.org/xml/rss.xml").text):
        t = parse_t(e.get("fromdate") or e.get("pubDate"))
        mod = parse_t(e.get("datemodified") or e.get("pubDate"))
        if (mod or t) and (mod or t) < now() - timedelta(days=HISTORY_D): continue
        lvl = (e.get("alertlevel") or "").lower()
        base = {"green": 15, "orange": 50, "red": 75}.get(lvl, 15)
        try:
            pop = float(e.get("population@value") or 0)
            if pop > 1e6: base += 15
            elif pop > 1e5: base += 8
        except Exception: pop = None
        lat = float(e["lat"]) if e.get("lat") else None; lon = float(e["long"]) if e.get("long") else None
        sev = e.get("severity@value")
        out.append(item("GDACS", "GDACS", f"{e.get('eventtype')}{e.get('eventid')}|{e.get('episodeid')}", strip(e.get("title")),
                        "natural disaster", e.get("link"), t, lat, lon, e.get("country"), base,
                        extra={"alertlevel": lvl, "eventtype": e.get("eventtype"), "eventid": e.get("eventid"),
                               "mag": float(sev) if (sev and e.get("eventtype") == "EQ") else None, "population": pop}))
    return out

def f_cisa_kev():
    j = get("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json").json()
    out = []
    for v in j["vulnerabilities"]:
        t = parse_t(v.get("dateAdded") + "T00:00:00Z")
        if t < now() - timedelta(days=HISTORY_D): continue
        base = 30 + (15 if v.get("knownRansomwareCampaignUse") == "Known" else 0)
        out.append(item("CISA KEV", "CISA", v["cveID"], f"{v['cveID']} added to CISA KEV: {v.get('vendorProject')} {v.get('product')} - {v.get('vulnerabilityName')}",
                        "cyber", f"https://nvd.nist.gov/vuln/detail/{v['cveID']}", t, location="Global (software)", base=base,
                        extra={"ransomware": v.get("knownRansomwareCampaignUse"), "due": v.get("dueDate"), "kev_catalog": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"}))
    return out

def f_cisa_adv():
    out = rss_generic("CISA Advisories", "CISA", "https://www.cisa.gov/cybersecurity-advisories/all.xml", "cyber", 20, True,
                      force_cat=True, kwboost=r"emergency directive|actively exploited|critical infrastructure|nation-state|ransomware")
    return out

def f_eonet():
    j = get(f"https://eonet.gsfc.nasa.gov/api/v3/events?status=open&days={HISTORY_D}").json()
    out = []
    for ev in j["events"]:
        g = ev["geometry"][-1]; cat = ev["categories"][0]["id"]
        lat = lon = None
        if g["type"] == "Point": lon, lat = g["coordinates"][:2]
        else: lat, lon = centroid(g)
        base = {"severeStorms": 30, "volcanoes": 30, "wildfires": 12, "floods": 30, "earthquakes": 25, "seaLakeIce": 5}.get(cat, 15)
        mv = g.get("magnitudeValue")
        if cat == "severeStorms" and mv: base += min(35, max(0, (mv - 34) * 0.4))
        out.append(item("NASA EONET", "NASA", ev["id"], ev["title"], "natural disaster",
                        (ev["sources"][0]["url"] if ev.get("sources") else ev["link"]), parse_t(g["date"]), lat, lon, None, base,
                        extra={"eonet_category": cat, "magnitude": mv, "unit": g.get("magnitudeUnit"), "api": ev["link"]}))
    return out

def f_reliefweb():
    out = rss_generic("ReliefWeb Disasters", "ReliefWeb", "https://reliefweb.int/disasters/rss.xml", "natural disaster", 35, True, maxage_d=HISTORY_D)
    out += rss_generic("ReliefWeb Updates", "ReliefWeb", "https://reliefweb.int/updates/rss.xml", "other", 12, False,
                       kwboost=r"flash update|emergency|outbreak|earthquake|cyclone|displac")
    return out

TG_CHANNELS = ["OSINTdefender", "ClashReport", "warmonitors", "intelslava"]
TG_EXTRA = ["Middle_East_Spectator", "rnintel", "BellumActaNews", "CIG_telegram", "AuroraIntel", "insiderpaper", "disclosetv",
            "spectatorindex", "TheIslanderNews", "nexta_live", "QudsNen"]
def f_telegram():
    out = []; errs = []
    import sources_ext as X
    for ch in TG_CHANNELS + TG_EXTRA:
        try:
            h = get(f"https://t.me/s/{ch}").text
            for blk in re.split(r'<div class="tgme_widget_message_wrap', h)[1:]:
                post = re.search(r'data-post="([^"]+)"', blk)
                txt = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', blk, re.S)
                tm = re.search(r'datetime="([^"]+)"', blk)
                if not post or not txt: continue
                t = parse_t(tm.group(1)) if tm else None
                if t and t < now() - timedelta(days=2): continue
                text = strip(txt.group(1))
                text = re.split(r"💧|Rainbet|Use our affiliate|Join us|Follow us", text)[0].strip()   # drop sponsor/promo footers
                if len(text) < 25 or re.search(r"casino|sportsbook|affiliate|promo code", text, re.I): continue
                urls = [u for u in re.findall(r'href="([^"]+)"', txt.group(1)) if not u.startswith("?")]
                media = bool(re.search(r"tgme_widget_message_(photo|video)", blk))
                it = X.social_item(f"Telegram @{ch}", post.group(1), text[:280], f"https://t.me/{post.group(1)}", t, urls, text,
                                   base=20, extra={"channel": ch}, media_flag=media)
                if it: out.append(it)
        except Exception as ex:
            errs.append(f"{ch}: {ex}")
    if errs and not out: raise RuntimeError("; ".join(errs))
    return out, ({"channel_errors": errs} if errs else {})

SOURCES = [
    ("USGS earthquakes (significant_day + 4.5_day GeoJSON)", "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson", f_usgs),
    ("NWS CAP alerts (api.weather.gov, Severe/Extreme)", "https://api.weather.gov/alerts/active?severity=Extreme,Severe", f_nws),
    ("tsunami.gov NTWC/PTWC Atom", "https://www.tsunami.gov/events/xml/PAAQAtom.xml", f_tsunami),
    ("NOAA SWPC alerts + Kp", "https://services.swpc.noaa.gov/products/alerts.json", f_swpc),
    ("WHO Disease Outbreak News (API)", "https://www.who.int/api/news/diseaseoutbreaknews", f_who),
    ("CIDRAP News topic RSS (Ebola, H5N1, Marburg, Measles, Mpox, Nipah, Cholera, Emerging, Pandemic flu)", "https://www.cidrap.umn.edu/rss-feeds", f_cidrap),
    ("GDACS RSS", "https://www.gdacs.org/xml/rss.xml", f_gdacs),
    ("CISA KEV JSON", "https://www.cisa.gov/known-exploited-vulnerabilities-catalog", f_cisa_kev),
    ("CISA Advisories RSS", "https://www.cisa.gov/cybersecurity-advisories/all.xml", f_cisa_adv),
    ("NASA EONET v3", "https://eonet.gsfc.nasa.gov/api/v3/events", f_eonet),
    ("ReliefWeb RSS (disasters + updates)", "https://reliefweb.int/updates/rss.xml", f_reliefweb),
    ("Telegram public previews (t.me/s/: " + ", ".join(TG_CHANNELS + TG_EXTRA) + ")", "https://t.me/s/OSINTdefender", f_telegram),
]
# Tested and not usable (recorded for transparency; see SOURCES.md)
FAILED_SOURCES = [
    ("CIDRAP site-wide RSS", "https://www.cidrap.umn.edu/rss.xml", "Reachable but stale (newest item 2022) - replaced by CIDRAP topic feeds"),
    ("ProMED RSS", "https://promedmail.org/feed/", "308 -> 404; no public RSS (ProMED moved to a subscription platform)"),
    ("ReliefWeb API v1", "https://api.reliefweb.int/v1/reports", "HTTP 410 Gone (v1 retired; v2 requires a registered appname) - RSS used instead"),
    ("WHO DON legacy RSS", "https://www.who.int/feeds/entity/csr/don/en/rss.xml", "HTTP 404 - WHO JSON API used instead"),
    ("EpiWatch", "https://www.epiwatch.org/", "JavaScript single-page app, no public machine-readable feed found"),
    ("BEACON", "https://beaconbio.org/", "HTML site, no public machine-readable feed found"),
    ("X/Twitter public search (nitter.net)", "https://nitter.net/search?q=explosion", "HTTP 200 but returns no tweets (blocked/empty); no simple no-login route"),
    ("Telegram @sentdefender, @IntelRepublic", "https://t.me/s/sentdefender", "302 redirect - web preview disabled"),
]

# ---------------------------------------------------------------- db
def db():
    c = sqlite3.connect(DB, timeout=30); c.row_factory = sqlite3.Row
    c.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, source TEXT, family TEXT, title TEXT, category TEXT, source_url TEXT,
      event_time TEXT, lat REAL, lon REAL, location TEXT, base INTEGER, official INTEGER, extra TEXT,
      first_seen TEXT, last_seen TEXT, cluster_id TEXT);
    CREATE INDEX IF NOT EXISTS ix_alerts_cluster ON alerts(cluster_id);
    CREATE INDEX IF NOT EXISTS ix_alerts_time ON alerts(event_time);
    CREATE TABLE IF NOT EXISTS clusters(cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL,
      event_time TEXT, first_seen TEXT, updated TEXT, score INTEGER, confidence TEXT, n_items INTEGER, n_families INTEGER,
      families TEXT, links TEXT, watchlist INTEGER, brief TEXT, high_at TEXT);
    CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY AUTOINCREMENT, started TEXT, finished TEXT, trigger TEXT,
      fetched INTEGER, new_items INTEGER, ok_sources INTEGER, failed_sources INTEGER, error TEXT);
    CREATE TABLE IF NOT EXISTS source_health(name TEXT PRIMARY KEY, url TEXT, ok INTEGER, items INTEGER, last_checked TEXT,
      last_ok TEXT, error TEXT, note TEXT);
    """)
    cols = {r[1] for r in c.execute("PRAGMA table_info(clusters)")}
    for col, typ in (("rising", "INTEGER DEFAULT 0"), ("mentions_3h", "INTEGER DEFAULT 0"), ("eff_families", "INTEGER DEFAULT 0"), ("rank", "INTEGER DEFAULT 0"), ("pushed_at", "TEXT")):
        if col not in cols: c.execute(f"ALTER TABLE clusters ADD COLUMN {col} {typ}")
    return c

# ---------------------------------------------------------------- clustering
STOP = set(("the a an of in on at to for and or with by from is are was were has have be this that as near region update new km "
            "live breaking news watch latest today now video stream hours says said report reports").split())
_TOK = {}
def toks(s):
    if s in _TOK: return _TOK[s]
    out = set()
    for w in re.findall(r"[a-z0-9]{3,}", (s or "").lower().replace("’s", "").replace("'s", "")):
        if w in STOP: continue
        if len(w) > 4 and w.endswith("s"): w = w[:-1]
        out.add(w)
    if len(_TOK) > 50000: _TOK.clear()
    _TOK[s] = out
    return out
def jacc(a, b):
    A, B = toks(a), toks(b)
    return len(A & B) / len(A | B) if A and B else 0
def dist_km(a, b, c, d):
    r = math.radians
    h = math.sin(r(c - a) / 2) ** 2 + math.cos(r(a)) * math.cos(r(c)) * math.sin(r(d - b) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(1, h)))

def matches(n, o):
    if n["category"] != o["category"] and jacc(n["title"], o["title"]) < 0.6: return False
    tn, to = parse_t(n["event_time"]), parse_t(o["event_time"])
    if tn and to and abs((tn - to).total_seconds()) > WINDOW_H * 3600: return False
    en, eo = json.loads(n["extra"] or "{}"), json.loads(o["extra"] or "{}")
    hasgeo = None not in (n["lat"], n["lon"], o["lat"], o["lon"])
    # earthquakes: strict physical match (time, place, magnitude)
    mn, mo = en.get("mag"), eo.get("mag")
    if mn and mo:
        if not (tn and to and abs((tn - to).total_seconds()) <= 3600): return False
        if hasgeo and dist_km(n["lat"], n["lon"], o["lat"], o["lon"]) > 200: return False
        return abs(mn - mo) <= 0.7 and (hasgeo or jacc(n["title"], o["title"]) >= 0.2)
    if mn or mo:  # one is a quake, the other not quake-typed -> only if same place+time
        if not hasgeo: return False
        return (tn and to and abs((tn - to).total_seconds()) <= 3 * 3600) and dist_km(n["lat"], n["lon"], o["lat"], o["lon"]) < 150 and "earthquake" in (n["title"] + o["title"]).lower()
    if n["family"] == o["family"] == "NOAA" and en.get("event") and eo.get("event"):
        if en["event"] != eo["event"]: return False
        if en.get("sender") and en.get("sender") == eo.get("sender"): return True   # same NWS office, same hazard
        return hasgeo and dist_km(n["lat"], n["lon"], o["lat"], o["lon"]) < 60
    j = jacc(n["title"], o["title"])
    if hasgeo:
        return dist_km(n["lat"], n["lon"], o["lat"], o["lon"]) < 400 and j >= 0.25
    shared = len(toks(n["title"]) & toks(o["title"]))
    return j >= 0.5 or (shared >= 4 and j >= 0.2)

def assign_clusters(c, new_items):
    lo = iso(now() - timedelta(hours=WINDOW_H * 2 + 24))
    pool = [dict(r) for r in c.execute("SELECT * FROM alerts WHERE COALESCE(event_time, first_seen) >= ?", (lo,))]
    touched = set()
    for n in new_items:
        n = dict(c.execute("SELECT * FROM alerts WHERE id=?", (n["id"],)).fetchone())
        cid = None
        for o in pool:
            if o["id"] == n["id"] or not o.get("cluster_id"): continue
            if matches(n, o): cid = o["cluster_id"]; break
        cid = cid or n["id"]
        c.execute("UPDATE alerts SET cluster_id=? WHERE id=?", (cid, n["id"]))
        n["cluster_id"] = cid
        for o in pool:
            if o["id"] == n["id"]: o["cluster_id"] = cid
        if n["id"] not in [o["id"] for o in pool]: pool.append(n)
        touched.add(cid)
    return touched

def et(s):
    d = parse_t(s)
    if not d: return "time not reported"
    # US Eastern (DST-aware via zoneinfo)
    from zoneinfo import ZoneInfo
    return d.strftime("%Y-%m-%d %H:%M UTC") + " / " + d.astimezone(ZoneInfo("America/New_York")).strftime("%b %d %I:%M %p ET")

def rebuild_cluster(c, cid):
    rows = [dict(r) for r in c.execute("SELECT * FROM alerts WHERE cluster_id=? ORDER BY base DESC, event_time", (cid,))]
    if not rows: return
    top = rows[0]
    fams = sorted({r["family"] for r in rows})
    official = any(r["official"] for r in rows)
    # uncited social posts and volume-surge signals never count as independent confirmation
    eff = sorted(set(fams) - {"social", "GDELT-volume"})
    nf = len(eff)
    exs = [json.loads(r["extra"] or "{}") for r in rows]
    n_social = sum(1 for e in exs if e.get("tier") == "social")
    # rising: >=3 reports from >=2 sources in last 3h and more than in the 3-12h before
    t3, t12 = now() - timedelta(hours=3), now() - timedelta(hours=12)
    # items whose time is only the scan time (YouTube live search) carry no publication-time signal
    rt = [(parse_t(r["event_time"]) or parse_t(r["first_seen"]), r["source"]) for r, e in zip(rows, exs) if not e.get("live")]
    recent = [s for t, s in rt if t and t >= t3]
    prior = [s for t, s in rt if t and t12 <= t < t3]
    rising = (len(recent) >= 3 and len(set(recent)) >= 2 and len(recent) > len(prior)) or any(e.get("rising") for e in exs)
    score = max(r["base"] for r in rows)
    # independent confirmation
    # independent confirmation bonus, proportional to impact so a confirmed minor event stays minor
    tiers = {e.get("tier") for e in exs}
    news_only = not official and "news" in tiers
    if news_only:
        # media outlets often syndicate one wire story; smaller bonus, and news-only clusters top out at 70
        if nf >= 3: score += 15
        elif nf == 2: score += 8
    elif nf >= 3: score += min(30, max(10, score * 0.6))
    elif nf == 2: score += min(20, max(8, score * 0.5))
    # speed of spread: 3+ reports from 2+ independent families within 3 hours
    times = sorted(t for t in (parse_t(r["event_time"]) for r in rows) if t)
    if len(rows) >= 3 and nf >= 2 and times and (times[-1] - times[0]) <= timedelta(hours=3): score += 10
    if rising: score += 10 if nf >= 2 else 5
    if nf >= 2: conf = "High" if official else "Medium"
    elif nf == 1 and official: conf = "High"
    else: conf = "Low"
    if conf == "Low": score = min(score, 45)   # cap single-source / unconfirmed items (watchlist)
    if news_only: score = min(score, 70)
    if not official and not re.search(BOOST_RX, " ".join(r["title"] for r in rows), re.I):
        score = min(score, 55)   # media/social-only items without crisis phrasing cannot be "high" on the 0-100 score
    score = max(0, min(100, int(score)))
    rank = rank_cluster(rows, exs, score, conf, nf, official, news_only, rising, tiers)
    if nf == 1 and official and top["family"] in ("CIDRAP", "ReliefWeb"): conf = "Medium"
    watch = 1 if conf == "Low" else 0
    # suppression: rank 0-1 non-official items (local trivia / no threat signal) are stored but excluded from the watchlist and feed
    if rank <= 1 and not official: watch = 2
    geo = next((r for r in rows if r["lat"] is not None), None)
    links, seen = [], set()
    for r in rows:
        if r["source_url"] and r["source_url"] not in seen:
            seen.add(r["source_url"]); links.append({"source": r["source"], "url": r["source_url"]})
    ev = min((r["event_time"] for r in rows if r["event_time"]), default=None)
    loc = top["location"] or next((r["location"] for r in rows if r["location"]), None)
    brief = None
    if (score >= HIGH or rank >= 7) and watch == 0:
        where = loc or "location not specified by source"
        if geo: where += f" (approx. {geo['lat']:.2f}, {geo['lon']:.2f})"
        ex = json.loads(top["extra"] or "{}")
        facts = []
        for k, lab in (("mag", "magnitude"), ("pager", "USGS PAGER alert"), ("alertlevel", "GDACS alert level"), ("severity", "NWS severity"),
                       ("urgency", "urgency"), ("event", "event type"), ("scale_level", "NOAA scale level"), ("kp", "Kp"),
                       ("tsunami_category", "tsunami message category"), ("ransomware", "known ransomware use"), ("due", "CISA remediation due")):
            if ex.get(k) not in (None, "", 0, "Unknown"): facts.append(f"{lab}: {ex[k]}")
        if ex.get("near_local"): facts.append("covers the configured local area")
        brief = (f"WHAT: {top['title']}" + (f" [{'; '.join(facts)}]" if facts else "") +
                 f". WHERE: {where}. WHEN: {et(ev)}. CONFIDENCE: {conf} — reported by {len(rows)} item(s) from {nf} independent "
                 f"source famil{'y' if nf == 1 else 'ies'} ({', '.join(eff)})" + (f" plus {n_social} social post(s)" if n_social else "") +
                 (f"; RISING: {len(recent)} reports in the last 3h" if rising else "") + f"; severity {score}/100, rank {rank}/10. VERIFY: " +
                 " | ".join(l["url"] for l in links[:5]))
    prev = c.execute("SELECT first_seen, high_at, pushed_at FROM clusters WHERE cluster_id=?", (cid,)).fetchone()
    pushed_at = prev["pushed_at"] if prev else None   # preserved across re-scoring (INSERT OR REPLACE rewrites the row)
    first_seen = prev["first_seen"] if prev else min(r["first_seen"] for r in rows)
    high_at = prev["high_at"] if prev and prev["high_at"] else (iso(now()) if (score >= HIGH or rank >= 7) and watch == 0 else None)
    c.execute("""INSERT OR REPLACE INTO clusters(cluster_id,title,category,location,lat,lon,event_time,first_seen,updated,score,confidence,
                 n_items,n_families,families,links,watchlist,brief,high_at,rising,mentions_3h,eff_families,rank,pushed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (cid, top["title"], top["category"], loc, geo["lat"] if geo else None, geo["lon"] if geo else None, ev, first_seen,
               iso(now()), score, conf, len(rows), nf, json.dumps(fams), json.dumps(links), watch, brief, high_at,
               1 if rising else 0, len(recent), nf, rank, pushed_at))

def rank_cluster(rows, exs, score, conf, nf, official, news_only, rising, tiers):
    """Deterministic 0-10 rank. Documented in README.md (Severity rank)."""
    text = " ".join(r["title"] for r in rows)
    cat = rows[0]["category"]
    r = min(8, round(score / 12))                         # default: from the 0-100 score
    mags = [e.get("mag") for e in exs if e.get("mag")]
    if mags:                                              # earthquakes: magnitude + USGS PAGER is the blast radius
        m = max(mags)
        r = 2 if m < 5 else 3 if m < 5.5 else 4 if m < 6 else 5 if m < 7 else 6 if m < 8 else 8
        pagers = {e.get("pager") for e in exs}
        if "red" in pagers: r = max(r, 8)
        elif "orange" in pagers: r = max(r, 7)
        elif "yellow" in pagers: r = max(r, 6)
    tc = {e.get("tsunami_category") for e in exs}
    if "warning" in tc or "threat" in tc: r = max(r, 8)
    elif tc & {"advisory", "watch"}: r = max(r, 6)
    lv = {e.get("alertlevel") for e in exs}
    if not mags and "red" in lv:
        r = max(r, 7)
        pm = re.search(r"is ([\d.]+) million", text)
        if pm and float(pm.group(1)) >= 1: r = max(r, 8)
    elif not mags and "orange" in lv: r = max(r, 5)
    nws = [e for e in exs if e.get("event")]
    if nws:
        ev = " ".join(e["event"] for e in nws)
        r = 6 if re.search(r"Tornado Emergency|Hurricane Warning|Extreme Wind|Tsunami Warning|Storm Surge Warning", ev) else \
            5 if any(e.get("severity") == "Extreme" for e in nws) else 4
        if any(e.get("near_local") for e in nws): r += round(scope_cfg()[1])   # local-area relevance; config local_boost, 0 in global scope
    if cat == "space weather":
        lvl = max([e.get("scale_level") or 0 for e in exs] + [0])
        kp = max([e.get("kp") or 0 for e in exs] + [0])
        if kp >= 9: lvl = max(lvl, 5)
        elif kp >= 8: lvl = max(lvl, 4)
        r = {0: 1, 1: 2, 2: 3, 3: 5, 4: 7, 5: 9}[lvl]
    if cat == "disease":
        if "WHO" in {x["family"] for x in rows}: r = max(r, 5)
        if re.search(HIGH_CONSEQ, text, re.I):
            who_or_broad = "WHO" in {x["family"] for x in rows} or nf >= 3
            r = max(r, 6 if who_or_broad else 5 if (official or nf >= 2) else r)
            if who_or_broad and re.search(r" and |, ", text): r = max(r, 7)   # multi-country spread, WHO-confirmed or 3+ independent sources
        if re.search(r"pandemic declared|declares? (a )?pandemic|PHEIC|public health emergency of international concern", text, re.I): r = max(r, 9)
    if cat == "cyber":
        r = 3
        if any(e.get("ransomware") == "Known" for e in exs): r = 4
        if re.search(r"emergency directive", text, re.I): r = 6
        if re.search(r"nationwide (outage|blackout)|grid (attack|down)|critical infrastructure (attack|compromise)", text, re.I): r = 7
    boost = re.search(BOOST_RX, text, re.I)
    if boost:
        br = 7 if not re.search(r"ballistic missile|stampede|tsunami warning", text, re.I) else 6
        if re.search(PAST_RX, text, re.I): br = min(br, 5)   # coverage of a past event (trial, verdict, anniversary)
        r = max(r, br)
    elif not official:
        r = min(r, 4)                                     # media/social items without crisis phrasing stay minor/regional
    if re.search(r"nuclear (war|strike|attack|detonation)", text, re.I): r = max(r, 9)
    if re.search(r"nuclear war (is )?imminent|nuclear exchange", text, re.I): r = 10
    if rising and nf >= 2: r += 1                         # speed of spread, independently confirmed
    # confirmation caps
    if conf == "Low": r = min(r, 4)                       # single-source / unconfirmed rumors never reach 5+
    elif not official: r = min(r, 6 if nf < 3 else 8)     # media/social-only needs 3+ independent outlets for 7-8; 9-10 needs official corroboration
    # noise filter for non-official items with no strong crisis phrasing
    if not official and tiers <= {"news", "social", "aggregate"} and not re.search(BOOST_RX, text, re.I):
        if re.search(TRIVIA_RX, text, re.I): r = 0
        elif not re.search(THREAT_RX, text, re.I): r = min(r, 1)
    return max(0, min(10, int(r)))

# ---------------------------------------------------------------- scan
def scan(trigger="scheduled"):
    if not SCAN_LOCK.acquire(blocking=False):
        return {"status": "busy"}
    try:
        c = db(); started = iso(now())
        allitems, ok, bad = [], 0, 0
        for name, url, fn in SOURCES:
            try:
                res = fn(); note = {}
                if isinstance(res, tuple): res, note = res
                allitems += res; ok += 1
                c.execute("INSERT OR REPLACE INTO source_health VALUES(?,?,?,?,?,?,?,?)",
                          (name, url, 1, len(res), iso(now()), iso(now()), None, json.dumps(note) if note else None))
            except Exception as ex:
                bad += 1
                prev = c.execute("SELECT last_ok FROM source_health WHERE name=?", (name,)).fetchone()
                c.execute("INSERT OR REPLACE INTO source_health VALUES(?,?,?,?,?,?,?,?)",
                          (name, url, 0, 0, iso(now()), prev["last_ok"] if prev else None, f"{type(ex).__name__}: {str(ex)[:300]}", None))
        for name, url, why in FAILED_SOURCES:
            c.execute("INSERT OR REPLACE INTO source_health VALUES(?,?,?,?,?,?,?,?)", (name, url, -1, 0, iso(now()), None, why, "disabled after test"))
        new = ingest_items(c, allitems)
        cut = iso(now() - timedelta(days=HISTORY_D))
        c.execute("DELETE FROM alerts WHERE COALESCE(event_time, first_seen) < ? AND last_seen < ?", (cut, cut))
        c.execute("DELETE FROM clusters WHERE cluster_id NOT IN (SELECT DISTINCT cluster_id FROM alerts WHERE cluster_id IS NOT NULL)")
        c.execute("DELETE FROM scans WHERE started < ?", (cut,))
        c.execute("INSERT INTO scans(started,finished,trigger,fetched,new_items,ok_sources,failed_sources,error) VALUES(?,?,?,?,?,?,?,?)",
                  (started, iso(now()), trigger, len(allitems), len(new), ok, bad, None))
        c.commit(); c.close()
        return {"status": "ok", "started": started, "fetched": len(allitems), "new": len(new), "ok_sources": ok, "failed_sources": bad}
    except Exception as ex:
        traceback.print_exc()
        return {"status": "error", "error": str(ex)}
    finally:
        SCAN_LOCK.release()

def ingest_items(c, allitems):
    """Insert/update normalized items, cluster new ones, rebuild touched clusters. Returns list of new items."""
    if True:
        new = []
        ts = iso(now())
        seen_ids = set()
        for it in allitems:
            if it["id"] in seen_ids: continue
            seen_ids.add(it["id"])
            r = c.execute("SELECT id FROM alerts WHERE id=?", (it["id"],)).fetchone()
            if r:
                c.execute("UPDATE alerts SET last_seen=?, base=?, extra=?, title=?, location=?, family=?, official=? WHERE id=?",
                          (ts, it["base"], it["extra"], it["title"], it["location"], it["family"], it["official"], it["id"]))
            else:
                c.execute("""INSERT INTO alerts VALUES(:id,:source,:family,:title,:category,:source_url,:event_time,:lat,:lon,:location,
                             :base,:official,:extra,:fs,:fs,NULL)""", {**it, "fs": ts})
                new.append(it)
        new.sort(key=lambda x: x["event_time"] or "")
        touched = assign_clusters(c, new)
        # also refresh clusters whose members were updated this scan
        touched |= {r[0] for r in c.execute("SELECT DISTINCT cluster_id FROM alerts WHERE last_seen=? AND cluster_id IS NOT NULL", (ts,))}
        for cid in touched: rebuild_cluster(c, cid)
        return new

if __name__ != "__main__":
    import sources_ext as _X
    SOURCES += _X.EXT_SOURCES
    FAILED_SOURCES += _X.EXT_FAILED

if __name__ == "__main__":
    import scanner as _mod   # run via the importable module so the extended source list loads once
    res = _mod.scan("cli")
    import push; res["push"] = push.push_new()
    print(json.dumps(res, indent=1))
