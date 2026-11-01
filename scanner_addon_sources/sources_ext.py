"""Expanded Blackout sources: social (Reddit RSS, Bluesky, Mastodon, more Telegram, YouTube live search),
broad web (GDELT DOC 2.0, Google News RSS), regulators/official (Fed, SEC, FDIC, State Dept, DHS NTAS).
All public, no keys, no logins."""
import re, json, time, html
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, quote
import scanner as S

SOCIAL_DOMAINS = ("reddit.com", "redd.it", "x.com", "twitter.com", "t.me", "telegram", "bsky.app", "bsky.social", "youtube.com", "youtu.be",
                  "facebook.com", "instagram.com", "tiktok.com", "mastodon", "imgur.com", "discord", "threads.net", "rumble.com", "news.google.com",
                  # shorteners / paste / promo links are not primary sources
                  "bit.ly", "tinyurl.com", "t.co", "ow.ly", "buff.ly", "linktr.ee", "justpaste", "rainbet", "patreon.com", "ko-fi.com", "paypal")
MEDIA_HOSTS = ("i.redd.it", "v.redd.it", "youtube.com", "youtu.be", "imgur.com", "streamable.com")

def domain(u):
    try:
        d = urlparse(u).netloc.lower()
        return d[4:] if d.startswith("www.") else d
    except Exception:
        return ""
def is_social(d): return any(s in d for s in SOCIAL_DOMAINS)
def cited_domain(urls):
    for u in urls:
        d = domain(u)
        if d and not is_social(d): return d
    return None
def has_media(urls): return any(any(m in domain(u) for m in MEDIA_HOSTS) for u in urls)

def social_item(source, nid, title, url, t, urls, text="", base=15, live=False, extra=None, default_cat="other", media_flag=False):
    """Social-tier item. Family = cited primary-source domain, else 'social' (never counts as confirmation)."""
    cat = S.classify(title + " " + text, default_cat)
    if cat == "other": return None
    cd = cited_domain(urls)
    media = has_media(urls) or live or media_flag
    if cat in S.NEW_CATS and not (cd or media):   # new categories need a reliable link or eyewitness media
        return None
    b = base + (15 if re.search(S.BOOST_RX, title + " " + text, re.I) else 0)
    ex = {"tier": "social", "cited": cd, "media": media, "live": live, "text": text[:300], **(extra or {})}
    return S.item(source, cd or "social", nid, title, cat, url, t, base=b, official=False, extra=ex)

def news_item(source, publisher_domain, nid, title, url, t, base=15, extra=None, cat=None):
    c = cat or S.classify(title, "other")
    if c == "other": return None
    b = base + (20 if re.search(S.BOOST_RX, title, re.I) else 0)
    return S.item(source, publisher_domain or source, nid, title, c, url, t, base=b, official=False,
                  extra={"tier": "news", "publisher": publisher_domain, **(extra or {})})

# ---------------------------------------------------------------- Reddit (public RSS; JSON returns 403)
SUBS = ["worldnews", "news", "geopolitics", "CombatFootage", "UFOs", "UAP", "collapse", "preppers", "economics", "wallstreetbets",
        "earthquake", "TropicalWeather", "OSINT", "CredibleDefense", "religion", "ukraine", "Christianity", "islam", "conspiracy_commons"]
def f_reddit():
    url = f"https://www.reddit.com/r/{'+'.join(SUBS)}/new/.rss?limit=100"
    txt = S.get(url).text
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", txt, re.S):
        title = S.strip(re.search(r"<title>(.*?)</title>", e, re.S).group(1))
        link = re.search(r'<link href="([^"]+)"', e).group(1)
        sub = (re.search(r'label="(r/[^"]+)"', e) or [None, "r/?"])[1]
        t = S.parse_t((re.search(r"<published>(.*?)</published>", e) or [None, None])[1])
        content = html.unescape((re.search(r'<content type="html">(.*?)</content>', e, re.S) or [None, ""])[1])
        linkm = re.search(r'<a href="([^"]+)">\[link\]</a>', content)
        urls = [linkm.group(1)] if linkm else []
        body = S.strip(content)[:300]
        it = social_item(f"Reddit {sub}", link, title, link, t, urls, body, extra={"subreddit": sub, "linked": urls[:1]})
        if it: out.append(it)
    return out

# ---------------------------------------------------------------- Bluesky public search
BSKY_Q = ["breaking", "earthquake", "explosion", "coup", "martial law", "bank run", "UAP", "outbreak", "evacuation", "state of emergency"]
def f_bluesky():
    out = []
    for q in BSKY_Q:
        j = S.get(f"https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q={quote(q)}&limit=25&sort=latest").json()
        for p in j.get("posts", []):
            r = p.get("record", {}); text = r.get("text", "")
            urls = []
            emb = r.get("embed") or {}
            if emb.get("external", {}).get("uri"): urls.append(emb["external"]["uri"])
            for f in r.get("facets", []) or []:
                for ft in f.get("features", []):
                    if ft.get("uri"): urls.append(ft["uri"])
            media = "images" in json.dumps(emb) or "video" in json.dumps(emb)
            rkey = p["uri"].rsplit("/", 1)[-1]
            web = f"https://bsky.app/profile/{p['author']['handle']}/post/{rkey}"
            it = social_item(f"Bluesky @{p['author']['handle']}", p["uri"], text[:280], web, S.parse_t(r.get("createdAt")),
                             urls, text, extra={"query": q}, media_flag=media)
            if it: out.append(it)
    return out

# ---------------------------------------------------------------- Mastodon public hashtag timelines
MASTO_TAGS = ["breaking", "breakingnews", "earthquake", "ufo", "uap", "protest", "coup", "outbreak", "bankrun", "osint"]
def f_mastodon():
    out = []
    for tag in MASTO_TAGS:
        for st in S.get(f"https://mastodon.social/api/v1/timelines/tag/{tag}?limit=30").json():
            text = S.strip(st.get("content"))
            urls = re.findall(r'href="([^"]+)"', st.get("content") or "")
            urls = [u for u in urls if "/tags/" not in u and "/@" not in u]
            if st.get("card") and st["card"].get("url"): urls.insert(0, st["card"]["url"])
            ct = S.parse_t(st.get("created_at"))
            if ct and ct < S.now() - timedelta(days=2): continue   # boosted/old posts
            it = social_item(f"Mastodon @{st['account']['acct']}", st["id"], text[:280], st.get("url") or st.get("uri"),
                             S.parse_t(st.get("created_at")), urls, text, extra={"tag": tag}, media_flag=bool(st.get("media_attachments")))
            if it: out.append(it)
    return out

# ---------------------------------------------------------------- YouTube live search (no key, public results page)
YT_Q = ["breaking news live", "earthquake live", "explosion live", "protest live", "tsunami live", "missile attack live", "UFO live"]
def f_youtube_live():
    out = []
    for q in YT_Q:
        h = S.get(f"https://www.youtube.com/results?search_query={quote(q)}&sp=EgJAAQ%253D%253D").text
        m = re.search(r"var ytInitialData = (\{.*?\});</script>", h)
        if not m: raise RuntimeError("ytInitialData not found")
        vids = []
        def walk(o):
            if isinstance(o, dict):
                if "videoRenderer" in o: vids.append(o["videoRenderer"])
                for x in o.values(): walk(x)
            elif isinstance(o, list):
                for x in o: walk(x)
        walk(json.loads(m.group(1)))
        for v in vids[:12]:
            title = "".join(r.get("text", "") for r in v.get("title", {}).get("runs", []))
            ch = (v.get("ownerText", {}).get("runs") or [{}])[0].get("text", "?")
            vc = json.dumps(v.get("viewCountText", ""))
            live = "watching" in vc or "LIVE" in json.dumps(v.get("badges", []))
            if not live: continue
            watching = re.search(r'"([\d,]+)"\}, \{"text": " watching"', vc)
            url = f"https://www.youtube.com/watch?v={v['videoId']}"
            it = social_item(f"YouTube LIVE: {ch}", v["videoId"], f"[LIVE] {ch}: {title}", url, S.now(), [url], "", base=15, live=True,
                             extra={"channel": ch, "watching": watching.group(1) if watching else None, "query": q})
            if it: out.append(it)
    return out

# ---------------------------------------------------------------- more Telegram previews
TG_EXTRA = ["Middle_East_Spectator", "rnintel", "BellumActaNews", "CIG_telegram", "AuroraIntel", "insiderpaper", "disclosetv",
            "spectatorindex", "TheIslanderNews", "nexta_live", "QudsNen"]

# ---------------------------------------------------------------- Google News RSS per category
GN_Q = {
    "political": '(coup OR "martial law" OR assassination OR "state of emergency" OR "mass protests" OR "election crisis" OR curfew OR sanctions) when:1d',
    "financial": '("bank failure" OR "bank run" OR "circuit breaker" OR "trading halted" OR "currency crisis" OR "sovereign default" OR "emergency rate cut" OR "central bank emergency") when:1d',
    "spiritual/religious": '(sectarian violence OR "church attack" OR "mosque attack" OR "temple stampede" OR pilgrims stampede OR "religious festival" OR Vatican OR "pope") when:1d',
    "ufo/uap": '(UAP OR UFO OR AARO OR "unidentified anomalous") when:2d',
    "war/conflict": '(airstrike OR "missile strike" OR "drone attack" OR explosion OR "troops cross") when:1d',
    "disease": '(outbreak OR "mystery illness" OR "unknown disease" OR quarantine) when:1d',
}
def f_google_news():
    out = []
    for cat, q in GN_Q.items():
        txt = S.get(f"https://news.google.com/rss/search?q={quote(q)}&hl=en-US&gl=US&ceid=US:en").text
        for it in re.findall(r"<item>(.*?)</item>", txt, re.S):
            title = S.strip(re.search(r"<title>(.*?)</title>", it, re.S).group(1))
            link = S.strip(re.search(r"<link>(.*?)</link>", it, re.S).group(1))
            src = re.search(r'<source url="([^"]+)">(.*?)</source>', it, re.S)
            pub = S.strip(src.group(2)) if src else ""
            pd = domain(src.group(1)) if src else ""
            if pub and title.endswith(" - " + pub): title = title[: -len(pub) - 3]
            t = S.parse_t((re.search(r"<pubDate>(.*?)</pubDate>", it) or [None, None])[1])
            if t and t < S.now() - timedelta(days=2): continue
            n = news_item(f"Google News: {pub or pd}", pd, link, title, link, t, extra={"publisher_name": pub, "query_cat": cat})
            if n: out.append(n)
    return out

# ---------------------------------------------------------------- GDELT DOC 2.0 (1 request / 5 s)
GDELT_Q = {
    "political": '(coup OR "martial law" OR curfew OR "state of emergency" OR assassination)',
    "financial": '("bank run" OR "bank failure" OR "trading halt" OR "currency collapse" OR default)',
    "spiritual/religious": '("sectarian clashes" OR "church attack" OR "mosque attack" OR stampede)',
    "ufo/uap": '(UFO OR UAP OR "unidentified flying")',
    "disease": '("mystery illness" OR "unknown disease" OR outbreak)',
    "war/conflict": '(explosion OR airstrike OR "drone attack")',
}
SURGE_TERMS = ['"bank run"', '"martial law"', 'coup', '"mystery illness"', 'evacuation', 'stampede']
_last_gdelt = [0.0]
def gdelt(params):
    for attempt in range(2):
        wait = 10 - (time.time() - _last_gdelt[0])
        if wait > 0: time.sleep(wait)
        _last_gdelt[0] = time.time()
        r = S.get("https://api.gdeltproject.org/api/v2/doc/doc?" + params, timeout=25)   # 429 raises -> caller aborts GDELT for this scan
        if r.text.startswith("Please limit"): raise RuntimeError("GDELT rate limit (429)")
        return r.json() if r.text.strip() else {}
def f_gdelt():
    out = []; errs = []
    for cat, q in GDELT_Q.items():
        try:
            j = gdelt(f"query={quote(q + ' sourcelang:english')}&mode=artlist&format=json&maxrecords=40&timespan=6h&sort=datedesc")
        except Exception as ex:
            errs.append(f"{cat}: {ex}")
            if "429" in str(ex): raise RuntimeError("GDELT rate-limited this box's egress IP (HTTP 429): " + str(ex)[:120])
            continue
        for a in j.get("articles", []):
            t = S.parse_t(re.sub(r"^(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)Z$", r"\1-\2-\3T\4:\5:\6Z", a.get("seendate", "")))
            n = news_item(f"GDELT: {a.get('domain')}", a.get("domain"), a["url"], a.get("title", ""), a["url"], t,
                          base=15, extra={"sourcecountry": a.get("sourcecountry"), "query_cat": cat})
            if n: out.append(n)
    # surge detection by keyword: last 3h vs prior 21h (normalized volume)
    for term in SURGE_TERMS:
        try:
            j = gdelt(f"query={quote(term + ' sourcelang:english')}&mode=timelinevol&format=json&timespan=24h")
            series = (j.get("timeline") or [{}])[0].get("data", [])
            vals = [p["value"] for p in series]
            if len(vals) >= 12:
                k = max(1, len(vals) // 8)            # ~3h of 15-min buckets
                recent = sum(vals[-k:]) / k; prior = (sum(vals[:-k]) / max(1, len(vals) - k)) or 1e-9
                ratio = recent / prior
                if ratio >= 2.0 and recent > 0:
                    day = S.now().strftime("%Y%m%d%H")
                    out.append(S.item("GDELT volume surge", "GDELT-volume", f"surge|{term}|{day}",
                                      f"Rising coverage: {term.strip(chr(34))} mentions up {ratio:.1f}x in the last ~3h vs prior 21h (GDELT)",
                                      S.classify(term, "other") if S.classify(term, "other") != "other" else "political",
                                      f"https://api.gdeltproject.org/api/v2/doc/doc?query={quote(term)}&mode=artlist&timespan=3h&format=html",
                                      S.now(), base=20, official=False,
                                      extra={"tier": "aggregate", "surge_ratio": round(ratio, 2), "term": term, "rising": True}))
        except Exception as ex:
            errs.append(f"surge {term}: {ex}")
    if errs and not out: raise RuntimeError("; ".join(errs[:3]))
    return out, ({"errors": errs} if errs else {})

# ---------------------------------------------------------------- official / regulators
def f_fed():
    return S.rss_generic("Federal Reserve press", "FederalReserve", "https://www.federalreserve.gov/feeds/press_all.xml", "financial", 15, True,
                         force_cat=True, kwboost=r"emergency|liquidity|facility|discount window|stability|bank failure|unscheduled")
def f_sec():
    return S.rss_generic("SEC press releases", "SEC", "https://www.sec.gov/news/pressreleases.rss", "financial", 8, True,
                         force_cat=True, kwboost=r"trading suspension|emergency|halt|market-wide")
def f_fdic():
    j = S.get("https://banks.data.fdic.gov/api/failures?limit=10&sort_by=FAILDATE&sort_order=DESC&fields=NAME,CITYST,FAILDATE,COST,QBFASSET,CERT", allow_redirects=True).json()
    out = []
    for d in j.get("data", []):
        x = d["data"]; t = S.parse_t(datetime.strptime(x["FAILDATE"], "%m/%d/%Y").strftime("%Y-%m-%dT00:00:00Z"))
        if t < S.now() - timedelta(days=S.HISTORY_D): continue
        assets = x.get("QBFASSET") or 0
        base = 45 + (20 if assets and assets > 1e7 else 0)  # QBFASSET in $ thousands -> >$10B
        out.append(S.item("FDIC failed banks", "FDIC", x.get("CERT"), f"FDIC: bank failure - {x['NAME']} ({x['CITYST']})", "financial",
                          "https://www.fdic.gov/bank-failures/failed-bank-list", t, location=x["CITYST"], base=base,
                          extra={"tier": "official", "assets_thousands": assets}))
    return out
def f_state():
    out = []
    for e in S.rss_items(S.get("https://travel.state.gov/_res/rss/TAsTWs.xml").content):
        t = S.parse_t(e.get("pubDate")); title = S.strip(e.get("title"))
        if not t or t < S.now() - timedelta(days=S.HISTORY_D): continue
        lvl = re.search(r"Level (\d)", title); lv = int(lvl.group(1)) if lvl else 0
        if lv < 3: continue
        out.append(S.item("State Dept travel advisories", "StateDept", e.get("guid") or e.get("link"), f"US travel advisory updated: {title}", "political",
                          e.get("link"), t, location=title.split(" - ")[0], base=15 + (lv - 2) * 12, extra={"tier": "official", "level": lv}))
    return out
def f_ntas():
    txt = S.get("https://www.dhs.gov/ntas/1.1/alerts.xml").text
    out = []
    for a in re.findall(r"<alert[^s].*?</alert>", txt, re.S):
        title = S.strip((re.search(r"<summary>(.*?)</summary>", a, re.S) or [None, "NTAS alert"])[1])[:200]
        start = re.search(r'start="([^"]+)"', a)
        out.append(S.item("DHS NTAS", "DHS", a[:80], "DHS NTAS bulletin/alert: " + title, "political", "https://www.dhs.gov/national-terrorism-advisory-system",
                          S.parse_t(start.group(1)) if start else S.now(), location="United States", base=55, extra={"tier": "official"}))
    return out

# ---------------------------------------------------------------- added 2026-10-31 (approved candidates: JMA, GeoNet, IMO, Africa CDC, UK NCSC)
def _quake_base(m):   # same magnitude curve as scanner.f_usgs
    return 20 + max(0, (m - 4.5)) * 18
def _small_quake_base(m):   # below M4.5 scale down instead of flooring at 20 (GeoNet/IMO report small felt quakes)
    return max(5, int(20 + (m - 4.5) * 10)) if m < 4.5 else _quake_base(m)
JMA_SHINDO = {"1": 1, "2": 2, "3": 3, "4": 4, "5-": 5, "5+": 5.5, "6-": 6, "6+": 6.5, "7": 7}
def f_jma():
    """JMA bosai quake list (all bulletins) + tsunami list. Keeps the latest bulletin per event; M>=4.5 or max shindo >=4, and any Nankai Trough info."""
    out, seen = [], set()
    for x in S.get("https://www.jma.go.jp/bosai/quake/data/list.json").json():
        eid = x.get("eid")
        if not eid or eid in seen: continue
        seen.add(eid)
        t = S.parse_t(x.get("at") or x.get("rdt"))
        if not t or t < S.now() - timedelta(days=S.HISTORY_D): continue
        nankai = "南海トラフ" in (x.get("ttl") or "")
        try: m = float(x.get("mag") or 0)
        except ValueError: m = 0
        si = JMA_SHINDO.get(str(x.get("maxi") or ""), 0)
        if not (nankai or m >= 4.5 or si >= 4): continue
        lat = lon = None
        cm = re.match(r"([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)", x.get("cod") or "")
        if cm: lat, lon = float(cm.group(1)), float(cm.group(2))
        place = x.get("en_anm") or x.get("anm") or "Japan"
        if nankai:
            title, base = f"JMA: Nankai Trough earthquake information ({x.get('en_ttl') or x.get('ttl')})", 40
        else:
            title = f"JMA: M{m:g} earthquake - {place}" + (f", max seismic intensity {x.get('maxi')}" if si else "")
            base = _quake_base(m) + max(0, si - 4) * 10
        out.append(S.item("JMA earthquakes", "JMA", eid, title, "natural disaster", "https://www.jma.go.jp/bosai/map.html#contents=earthquake_map&lang=en",
                          t, lat, lon, place + ", Japan", base, extra={"mag": m, "max_shindo": x.get("maxi"), "bulletin": x.get("en_ttl") or x.get("ttl"), "json": x.get("json")}))
    for x in S.get("https://www.jma.go.jp/bosai/tsunami/data/list.json").json():
        t = S.parse_t(x.get("at") or x.get("rdt"))
        if not t or t < S.now() - timedelta(days=S.HISTORY_D): continue
        kinds = ", ".join(k.get("kind", "") for k in (x.get("kind") or []))[:200]
        out.append(S.item("JMA earthquakes", "JMA", "tsunami|" + (x.get("ctt") or "") + (x.get("eid") or ""),
                          f"JMA tsunami bulletin ({x.get('en_ttl') or x.get('ttl')}): {x.get('en_anm') or x.get('anm')} M{x.get('mag')}", "natural disaster",
                          "https://www.jma.go.jp/bosai/map.html#contents=tsunami&lang=en", t, location="Japan", base=45,
                          extra={"kinds": kinds}))
    return out

def f_geonet():
    """GeoNet NZ: felt quakes (MMI>=3, last HISTORY_D days, 'deleted' dropped) + volcanic alert levels >=1."""
    out = []
    for f in S.get("https://api.geonet.org.nz/quake?MMI=3", headers={"Accept": "application/vnd.geo+json;version=2"}).json().get("features", []):
        p = f["properties"]
        if p.get("quality") == "deleted": continue
        t = S.parse_t(p.get("time"))
        if not t or t < S.now() - timedelta(days=S.HISTORY_D): continue
        m = p.get("magnitude") or 0; mmi = p.get("mmi") or 0
        lon, lat = f["geometry"]["coordinates"][:2]
        out.append(S.item("GeoNet NZ", "GeoNet", p["publicID"], f"GeoNet: M{m:.1f} quake {p.get('locality')} (MMI {mmi})", "natural disaster",
                          f"https://www.geonet.org.nz/earthquake/{p['publicID']}", t, lat, lon, f"{p.get('locality')}, New Zealand",
                          _small_quake_base(m) + max(0, mmi - 5) * 8, extra={"mag": m, "mmi": mmi, "depth_km": p.get("depth")}))
    for f in S.get("https://api.geonet.org.nz/volcano/val", headers={"Accept": "application/vnd.geo+json;version=2"}).json().get("features", []):
        p = f["properties"]; lv = int(p.get("level") or 0)
        if lv < 1: continue
        lon, lat = f["geometry"]["coordinates"][:2]
        out.append(S.item("GeoNet NZ", "GeoNet", f"val|{p.get('volcanoID')}|{lv}", f"GeoNet: {p.get('volcanoTitle')} volcanic alert level {lv} - {p.get('activity')}",
                          "natural disaster", "https://www.geonet.org.nz/volcano", S.now(), lat, lon, f"{p.get('volcanoTitle')}, New Zealand",
                          5 + lv * 15, extra={"val": lv, "aviation_colour": p.get("acc"), "hazards": p.get("hazards")}))
    return out

def f_imo():
    """Icelandic Met Office open API (api.vedur.is): VONA aviation colour codes, VALS alert levels, M>=3 quakes (last HISTORY_D days)."""
    out = []
    names = {v["code"]: v for v in S.get("https://api.vedur.is/volcanoes/volcanoes").json()}
    cut = S.now() - timedelta(days=S.HISTORY_D)
    acc_base = {"GREEN": 10, "YELLOW": 25, "ORANGE": 45, "RED": 65}
    for v in S.get("https://api.vedur.is/volcanoes/vona").json():
        t = S.parse_t(v.get("published_at"))
        if not t or t < cut: continue
        code = (v.get("aviation_color") or {}).get("code") or "?"; vv = names.get(v.get("volcano_code"), {})
        lon, lat = ((vv.get("geom_point") or {}).get("coordinates") or [None, None])[:2]
        out.append(S.item("Icelandic Met Office", "IMO", f"vona|{v.get('id')}", f"IMO VONA: {vv.get('name') or v.get('volcano_code')} aviation colour code {code}",
                          "natural disaster", "https://en.vedur.is/earthquakes-and-volcanism/volcanoes/vona-notifications/", t, lat, lon,
                          f"{vv.get('name') or v.get('volcano_code')}, Iceland", acc_base.get(code, 15), extra={"aviation_color": code, "notice": v.get("notice_number")}))
    for v in S.get("https://api.vedur.is/volcanoes/vals").json():
        t = S.parse_t(v.get("published_at"))
        if not t or t < cut: continue
        a = v.get("alert_level_info") or {}; lv = int(a.get("level") or 0); vv = names.get(v.get("volcano_code"), {})
        lon, lat = ((vv.get("geom_point") or {}).get("coordinates") or [None, None])[:2]
        out.append(S.item("Icelandic Met Office", "IMO", f"vals|{v.get('id')}", f"IMO volcano alert level: {vv.get('name') or v.get('volcano_code')} {a.get('code_en')} ({a.get('description_en')})",
                          "natural disaster", "https://en.vedur.is/earthquakes-and-volcanism/volcanoes/", t, lat, lon,
                          f"{vv.get('name') or v.get('volcano_code')}, Iceland", 10 + lv * 15, extra={"vals": lv}))
    st = cut.strftime("%Y-%m-%dT%H:%M:%S"); en = S.now().strftime("%Y-%m-%dT%H:%M:%S")
    for f in S.get(f"https://api.vedur.is/quakes/events?start_time={st}&end_time={en}&size_min=3&format=json").json().get("features", []):
        p = f["properties"]; lon, lat = f["geometry"]["coordinates"][:2]; m = p.get("magnitude") or 0
        t = S.parse_t(p.get("time"))
        out.append(S.item("Icelandic Met Office", "IMO", f"q|{p.get('event_id')}", f"IMO: M{m:.1f} earthquake, Iceland", "natural disaster",
                          "https://en.vedur.is/earthquakes-and-volcanism/earthquakes/", t, lat, lon, "Iceland",
                          _small_quake_base(m), extra={"mag": m, "depth_km": p.get("depth")}))
    return out

def f_africacdc():
    # the site-wide /feed/ is empty; the news-item and disease-outbreak post-type feeds carry the content
    out, seen = [], set()
    for u in ("https://africacdc.org/news-item/feed/", "https://africacdc.org/disease-outbreak/feed/"):
        for it in S.rss_generic("Africa CDC", "AfricaCDC", u, "disease", 15, True,
                                kwboost=r"outbreak|ebola|marburg|mpox|cholera|public health emergency|continental emergency|PHECS"):
            if it["id"] not in seen: seen.add(it["id"]); out.append(it)
    return out

def f_ncsc():
    return S.rss_generic("UK NCSC", "NCSC", "https://www.ncsc.gov.uk/api/1/services/v1/all-rss-feed.xml", "cyber", 15, True,
                         force_cat=True, kwboost=r"actively exploit|critical|nation-state|ransomware|joint advisory|alert|urgent")

# ---- t225 (2026-10-31): vetted official sources promoted from source_candidates.json ----
def f_certeu():
    return S.rss_generic("CERT-EU advisories", "CERT-EU", "https://cert.europa.eu/publications/security-advisories-rss", "cyber", 15, True,
                         force_cat=True, kwboost=r"critical|actively exploit|zero-day|0-day|in the wild")
def f_jpcert():
    return S.rss_generic("JPCERT/CC alerts", "JPCERT", "https://www.jpcert.or.jp/english/rss/jpcert-en.rdf", "cyber", 15, True,
                         force_cat=True, kwboost=r"actively exploit|attack|incident|zero-day|critical")
def f_cccs():
    # high-volume feed (~50 items, mostly routine vendor patch advisories): low base, boost alerts / active exploitation
    return S.rss_generic("Canadian Centre for Cyber Security", "CCCS", "https://www.cyber.gc.ca/api/cccs/rss/v1/get?feed=alerts_advisories&lang=en",
                         "cyber", 8, True, force_cat=True, kwboost=r"^alert|\balert\b|actively exploit|critical|zero-day|ransomware")
def f_csn():
    """Chile CSN (Universidad de Chile): no JSON/RSS exists; parse the stable <table class="sismologia"> latest-quakes list on the home page.
    Local time is America/Santiago. Only M>=4.0 kept (below USGS's M4.5 global floor; adds felt Chilean quakes); detail page read for lat/lon/UTC."""
    from zoneinfo import ZoneInfo
    h = S.get("https://www.sismologia.cl/").content.decode("utf-8", "replace")
    tb = re.search(r'<table class="sismologia">(.*?)</table>', h, re.S)
    if not tb: raise RuntimeError("CSN: quake table not found (page layout changed)")
    out = []
    for href, lt, place, depth, mag in re.findall(r'<a href="(/sismicidad/informes/[^"]+)">([\d-]+ [\d:]+)</a><br>\s*(.*?)\s*</td>\s*<td>(\d+) km</td>\s*<td class="magnitud">([\d.]+)</td>', tb.group(1), re.S):
        m = float(mag)
        if m < 4.0: continue
        t = datetime.strptime(lt, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("America/Santiago")).astimezone(timezone.utc)
        if t < S.now() - timedelta(days=S.HISTORY_D): continue
        url = "https://www.sismologia.cl" + href; lat = lon = None
        try:
            d = re.sub(r"<[^>]+>", " ", S.get(url).content.decode("utf-8", "replace"))
            la = re.search(r"Latitud\s+(-?\d+\.\d+)", d); lo = re.search(r"Longitud\s+(-?\d+\.\d+)", d)
            if la and lo: lat, lon = float(la.group(1)), float(lo.group(1))
        except Exception: pass
        place = html.unescape(place.strip())
        out.append(S.item("CSN Chile", "CSN", href.rsplit("/", 1)[-1].split(".")[0], f"CSN: M{m:.1f} earthquake {place}, Chile (depth {depth} km)",
                          "natural disaster", url, t, lat, lon, place + ", Chile", _small_quake_base(m), extra={"mag": m, "depth_km": int(depth)}))
    return out


# ---- t248 (2026-10-31): directory-slice sources vetted in t238, approved by Matt ----
import os as _os
T248_UA = {"User-Agent": "Mozilla/5.0 (BlackoutNetwork early-warning research monitor; +https://blackout.network)"}
_HERE = _os.path.dirname(_os.path.abspath(__file__))
def _jload(p, d):
    try: return json.load(open(p))
    except Exception: return d
def _jsave(p, v):
    tmp = p + ".tmp"; json.dump(v, open(tmp, "w"), indent=1); _os.replace(tmp, p)
# quake solutions relayed by EMSC keep the authoring agency as family, so a relay never counts as independent confirmation
_AUTH_FAMILY = {"NEIC": "USGS", "GFZ": "GFZ", "INGV": "INGV", "ROM": "INGV"}

def f_emsc():
    """EMSC FDSN event service (seismicportal.eu), M>=4.5, last 3 days. Family = authoring agency (NEIC -> USGS)."""
    st = (S.now() - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S")
    j = S.get(f"https://www.seismicportal.eu/fdsnws/event/1/query?format=json&minmag=4.5&start={st}&limit=400&orderby=time",
              headers=T248_UA, timeout=30).json()
    out = []
    for f in j.get("features", []):
        p = f["properties"]; m = p.get("mag") or 0
        if m < 4.5: continue
        lon, lat = f["geometry"]["coordinates"][:2]; depth = abs(f["geometry"]["coordinates"][2]) if len(f["geometry"]["coordinates"]) > 2 else None
        region = (p.get("flynn_region") or "").title(); auth = (p.get("auth") or "EMSC").upper()
        out.append(S.item("EMSC", _AUTH_FAMILY.get(auth, "EMSC"), p.get("unid") or f.get("id"), f"EMSC: M{m:.1f} earthquake {region}",
                          "natural disaster", f"https://www.seismicportal.eu/eventdetails.html?unid={p.get('unid') or f.get('id')}",
                          S.parse_t(p.get("time")), lat, lon, region, _quake_base(m),
                          extra={"mag": m, "magtype": p.get("magtype"), "depth_km": depth, "author": auth}))
    return out

def f_geofon():
    """GFZ GEOFON bulletin RSS (latest 20 events, own network solutions), M>=4.5."""
    txt = S.get("https://geofon.gfz.de/eqinfo/list.php?fmt=rss", headers=T248_UA, timeout=30).text
    out = []
    for it in re.findall(r"<item>(.*?)</item>", txt, re.S):
        tm = re.search(r"<title>M ([\d.]+), (.*?)</title>", it); dm = re.search(r"<description>\s*(\S+ \S+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(\d+) km\s+(\w)", it)
        gid = re.search(r"<guid[^>]*>(.*?)</guid>", it); lk = re.search(r"<link>(.*?)</link>", it)
        if not (tm and dm and gid): continue
        m = float(tm.group(1))
        if m < 4.5: continue
        place = html.unescape(tm.group(2).strip())
        out.append(S.item("GFZ GEOFON", "GFZ", gid.group(1), f"GEOFON: M{m:.1f} earthquake {place}", "natural disaster",
                          html.unescape(lk.group(1)) if lk else f"https://geofon.gfz.de/eqinfo/event.php?id={gid.group(1)}",
                          S.parse_t(dm.group(1) + "Z"), float(dm.group(2)), float(dm.group(3)), place, _quake_base(m),
                          extra={"mag": m, "depth_km": int(dm.group(4)), "status": {"A": "automatic", "M": "manual", "C": "confirmed"}.get(dm.group(5), dm.group(5))}))
    return out

def f_ingv():
    """INGV FDSN event service, M>=3.0, last 3 days (Italy/Mediterranean in detail; INGV's own solutions for larger quakes elsewhere)."""
    st = (S.now() - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S")
    txt = S.get(f"https://webservices.ingv.it/fdsnws/event/1/query?format=text&minmag=3.0&starttime={st}&orderby=time&limit=300",
                headers=T248_UA, timeout=30).text
    out = []
    for ln in txt.splitlines():
        if not ln or ln.startswith("#"): continue
        c = ln.split("|")
        if len(c) < 13: continue
        try: m = float(c[10]); lat = float(c[2]); lon = float(c[3]); depth = float(c[4])
        except ValueError: continue
        if m < 3.0: continue
        place = c[12].strip()
        out.append(S.item("INGV", "INGV", c[0], f"INGV: M{m:.1f} earthquake {place}", "natural disaster",
                          f"https://terremoti.ingv.it/event/{c[0]}", S.parse_t(c[1] + "Z"), lat, lon, place, _small_quake_base(m),
                          extra={"mag": m, "magtype": c[9], "depth_km": depth}))
    return out

HANS_STATE = _os.path.join(_HERE, "hans_state.json")
_HANS_BASE = {"GREEN": 5, "YELLOW": 25, "ORANGE": 45, "RED": 65}
def f_hans():
    """USGS HANS elevated volcanoes. Emits only on a colour-code / alert-level change (state in hans_state.json).
    First run seeds the state silently (no items)."""
    cur = S.get("https://volcanoes.usgs.gov/hans-public/api/volcano/getElevatedVolcanoes", headers=T248_UA, timeout=30).json()
    st = _jload(HANS_STATE, None)
    seeding = st is None
    st = st or {"levels": {}, "coords": {}}
    out, seen = [], set()
    for v in cur:
        vn = str(v.get("vnum")); seen.add(vn)
        lvl = [v.get("color_code"), v.get("alert_level")]
        if vn not in st["coords"]:
            try:
                g = S.get(f"https://volcanoes.usgs.gov/hans-public/api/volcano/getVolcano/{vn}", headers=T248_UA, timeout=20).json()
                st["coords"][vn] = [g.get("latitude"), g.get("longitude"), g.get("region")]
            except Exception: st["coords"][vn] = [None, None, None]
        prev = (st["levels"].get(vn) or {}).get("level")
        if not seeding and prev != lvl:
            lat, lon, reg = st["coords"][vn]
            was = f" (was {prev[0]}/{prev[1]})" if prev else " (was NORMAL/GREEN)"
            out.append(S.item("USGS Volcano Hazards (HANS)", "USGS", f"hans|{vn}|{lvl[0]}|{lvl[1]}|{v.get('notice_identifier')}",
                              f"USGS: {v.get('volcano_name')} volcano alert {lvl[1]} / aviation colour code {lvl[0]}{was}", "natural disaster",
                              v.get("notice_url") or "https://volcanoes.usgs.gov/hans-public/", S.parse_t(v.get("sent_utc")), lat, lon,
                              ", ".join(x for x in (v.get("volcano_name"), reg) if x), _HANS_BASE.get((lvl[0] or "").upper(), 15),
                              extra={"aviation_color": lvl[0], "alert_level": lvl[1], "previous": prev, "observatory": v.get("obs_abbr")}))
        st["levels"][vn] = {"level": lvl, "name": v.get("volcano_name"), "notice": v.get("notice_identifier")}
    for vn in [k for k in st["levels"] if k not in seen]:   # dropped off the elevated list -> back to NORMAL/GREEN
        old = st["levels"].pop(vn)
        if seeding: continue
        lat, lon, reg = st["coords"].get(vn, [None, None, None])
        out.append(S.item("USGS Volcano Hazards (HANS)", "USGS", f"hans|{vn}|GREEN|NORMAL|{S.iso(S.now())[:13]}",
                          f"USGS: {old.get('name')} volcano lowered to NORMAL / GREEN (was {old['level'][0]}/{old['level'][1]})", "natural disaster",
                          "https://volcanoes.usgs.gov/hans-public/", S.now(), lat, lon, old.get("name"), 5,
                          extra={"aviation_color": "GREEN", "alert_level": "NORMAL", "previous": old["level"]}))
    _jsave(HANS_STATE, st)
    return (out, {"seeded": len(st["levels"])}) if seeding else (out, {"elevated": len(st["levels"])})

IODA = "https://api.ioda.inetintel.cc.gatech.edu/v2"
IODA_CACHE = _os.path.join(_HERE, "ioda_entities.json")
# noise filters (t238 vetting): no Google-traffic-only (gtr) signals, ignore events that began >72 h ago,
# country score >= 300 and >= 30 min; region score >= 10000 and >= 2 h
IODA_RULES = {"country": (300, 1800), "region": (10000, 7200)}
_GEO = {}
def _ioda_geo(et, name, cc):
    """Approximate point for an IODA entity: admin-1 label point (region) or country label point, from heatmap_data/. Needed so
    unrelated outages with near-identical short titles don't cluster (scanner clustering uses distance + title similarity)."""
    if not _GEO:
        try:
            _GEO["c"] = json.load(open(_os.path.join(_HERE, "heatmap_data", "countries.json")))
            a1 = {}
            for k, v in json.load(open(_os.path.join(_HERE, "heatmap_data", "admin1.json"))).items():
                for n in {v.get("name"), v.get("ascii"), *(v.get("alts") or [])}:
                    if n: a1.setdefault((k.split(".")[0], n.lower()), v.get("label"))
            _GEO["a"] = a1
        except Exception: _GEO["c"], _GEO["a"] = {}, {}
    pt = None
    if et == "region" and cc: pt = _GEO["a"].get((cc, (name or "").lower()))
    if not pt and cc: pt = (_GEO["c"].get(cc) or {}).get("label")
    return (pt[0], pt[1]) if pt else (None, None)
def f_ioda():
    """IODA (Georgia Tech) internet-outage events, country + region level, filtered. One item per entity per outage start."""
    t1 = int(time.time()); t0 = t1 - 72 * 3600
    cache = _jload(IODA_CACHE, {}); lookups = 0; out = []
    for et, (thr, dur) in IODA_RULES.items():
        evs = S.get(f"{IODA}/outages/events?from={t0}&until={t1}&entityType={et}&limit=1000", headers=T248_UA, timeout=60).json().get("data") or []
        groups = {}
        for e in evs:
            if e.get("datasource") == "gtr" or (e.get("start") or 0) < t0: continue
            if (e.get("score") or 0) < thr or (e.get("duration") or 0) < dur: continue
            k = (e["location"], int(e["start"]) // 3600)
            g = groups.setdefault(k, {"e": e, "ds": set(), "score": 0, "end": 0})
            g["ds"].add(e["datasource"]); g["score"] = max(g["score"], e["score"]); g["end"] = max(g["end"], e["start"] + e["duration"])
        for (loc, hr), g in groups.items():
            e = g["e"]; name = e.get("location_name") or loc
            code = loc.split("/", 1)[-1]; country = name
            cc = code if et == "country" else None
            if et == "region":
                if not isinstance(cache.get(loc), dict) and lookups < 25:
                    lookups += 1
                    try:
                        d = (S.get(f"{IODA}/entities/query?entityType=region&entityCode={code}", headers=T248_UA, timeout=20).json().get("data") or [{}])[0]
                        at = d.get("attrs") or {}
                        cache[loc] = {"country": at.get("country_name") or "", "cc": at.get("country_code") or ""}
                    except Exception: pass
                ent = cache.get(loc) if isinstance(cache.get(loc), dict) else {}
                country, cc = ent.get("country", ""), ent.get("cc") or None
            lat, lon = _ioda_geo(et, name, cc)
            place = f"{name}, {country}" if et == "region" and country else name
            hrs = (g["end"] - e["start"]) / 3600; ongoing = g["end"] >= t1 - 900
            ds = "+".join(sorted(g["ds"]))
            st = datetime.fromtimestamp(e["start"], timezone.utc)
            # short, place-led title: shared boilerplate words would make unrelated outages cluster on title similarity
            title = f"{place}: internet outage, {hrs:.1f} h (IODA)"
            out.append(S.item("IODA internet outages", "IODA", f"{loc}|{e['start']}", title, "cyber",
                              f"https://ioda.inetintel.cc.gatech.edu/{et}/{code}?from={e['start'] - 3600}&until={min(t1, g['end'] + 3600)}",
                              st, lat, lon, place, (18 if et == "country" else 12) + (5 if len(g["ds"]) > 1 else 0),
                              extra={"outage": True, "entity_type": et, "datasources": ds, "ioda_score": round(g["score"]), "duration_h": round(hrs, 1), "ongoing": ongoing}))
    if lookups: _jsave(IODA_CACHE, cache)
    return out

# approximate country centroids so MeteoAlarm items map and only cluster with nearby warnings
MA_FEEDS = {"austria": (47.6, 14.1), "belgium": (50.6, 4.6), "bosnia-herzegovina": (44.2, 17.8), "bulgaria": (42.7, 25.3), "croatia": (45.1, 15.6),
            "cyprus": (35.0, 33.2), "czechia": (49.8, 15.5), "denmark": (56.0, 10.0), "estonia": (58.7, 25.5), "finland": (63.0, 26.0),
            "france": (46.6, 2.4), "germany": (51.1, 10.4), "greece": (39.1, 22.0), "hungary": (47.2, 19.4), "iceland": (64.9, -18.6),
            "ireland": (53.2, -8.0), "israel": (31.4, 35.0), "italy": (42.8, 12.6), "latvia": (56.9, 24.6), "lithuania": (55.3, 23.9),
            "luxembourg": (49.8, 6.1), "malta": (35.9, 14.4), "moldova": (47.2, 28.5), "montenegro": (42.8, 19.3), "netherlands": (52.2, 5.5),
            "republic-of-north-macedonia": (41.6, 21.7), "norway": (64.5, 12.0), "poland": (52.1, 19.4), "portugal": (39.6, -8.0),
            "romania": (45.9, 25.0), "serbia": (44.0, 20.9), "slovakia": (48.7, 19.7), "slovenia": (46.1, 14.8), "spain": (40.2, -3.6),
            "sweden": (62.0, 15.0), "switzerland": (46.8, 8.2), "united-kingdom": (54.0, -2.5), "ukraine": (49.0, 31.4)}
_MA_LEVEL = {"Severe": "Orange", "Extreme": "Red"}
def _meteoalarm_one(slug):
    txt = S.get(f"https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-{slug}", headers=T248_UA, timeout=25).text
    groups = {}
    nowt = S.now()
    for en in re.findall(r"<entry>(.*?)</entry>", txt, re.S):
        def tag(t):
            m = re.search(rf"<cap:{t}>(.*?)</cap:{t}>", en, re.S); return html.unescape(m.group(1).strip()) if m else ""
        sev = tag("severity")
        if sev not in _MA_LEVEL or tag("status") != "Actual" or tag("message_type") == "Cancel": continue
        exp = S.parse_t(tag("expires"))
        if exp and exp < nowt: continue
        tt = re.search(r"<title>(?:Yellow|Orange|Red)\s+(.*?)\s+Warning issued for", en)   # e.g. "Orange Rain Warning issued for Spain - ..."
        ev = tt.group(1) if tt else re.sub(r"^((severe|extreme|moderate|yellow|orange|red|warning|for)\s+)+", "", tag("event").strip(), flags=re.I)
        if "awareness_type" in ev: ev = "weather"
        ev = re.sub(r"\s+(warning|alert)s?$", "", ev, flags=re.I).strip() or "weather"
        onset = S.parse_t(tag("onset") or tag("effective") or tag("sent"))
        k = (ev.lower(), sev, onset.strftime("%Y-%m-%d") if onset else "")
        g = groups.setdefault(k, {"ev": ev, "sev": sev, "areas": [], "onset": onset, "expires": exp})
        a = tag("areaDesc")
        if a and a not in g["areas"]: g["areas"].append(a)
        if onset and (not g["onset"] or onset < g["onset"]): g["onset"] = onset
        if exp and (not g["expires"] or exp > g["expires"]): g["expires"] = exp
    country = slug.replace("republic-of-north-macedonia", "North Macedonia").replace("-", " ").title().replace("Bosnia Herzegovina", "Bosnia and Herzegovina")
    lat, lon = MA_FEEDS[slug]; out = []
    for (evl, sev, day), g in groups.items():
        n = len(g["areas"]); areas = ", ".join(g["areas"][:3]) + (f" +{n - 3} more" if n > 3 else "")
        out.append(S.item("MeteoAlarm (EUMETNET)", "MeteoAlarm", f"{slug}|{evl}|{sev}|{day}",
                          f"{country}: {_MA_LEVEL[sev]} {g['ev'].lower()} warning, {n} area{'s' if n != 1 else ''} ({areas}) - MeteoAlarm",
                          "natural disaster", f"https://meteoalarm.org/en/live/region/{slug}", g["onset"], lat, lon, f"{country}: {areas}"[:200],
                          {"Severe": 25, "Extreme": 45}[sev] + min(10, n // 5),
                          extra={"event": f"{_MA_LEVEL[sev]} {g['ev']}", "severity": sev, "areas": n, "expires": S.iso(g["expires"]) if g["expires"] else None}))
    return out
def f_meteoalarm():
    """MeteoAlarm legacy Atom (CAP) per member country, Severe/Extreme (orange/red) only, unexpired.
    One item per country + hazard + level + onset day (areas aggregated) so a storm doesn't become dozens of items."""
    from concurrent.futures import ThreadPoolExecutor
    out, errs = [], []
    def one(s):
        try: return _meteoalarm_one(s)
        except Exception as ex: errs.append(f"{s}: {type(ex).__name__}"); return []
    with ThreadPoolExecutor(max_workers=5) as ex:
        for r in ex.map(one, list(MA_FEEDS)): out += r
    if len(errs) > len(MA_FEEDS) // 2: raise RuntimeError("MeteoAlarm: most country feeds failed: " + "; ".join(errs[:5]))
    return (out, {"feed_errors": errs}) if errs else out

# ---- t414 (2026-11-01): Matt-approved batch (JTWC, AFAD, PAGASA, CERT-FR, UKHSA, Geoscience Australia, Taiwan CWA, NCSC-NL, HKCERT) ----
_T414_LAST = {}
def _polite(key, min_s=2.0):
    """per-host spacing between requests inside one scan (polite rate limit)"""
    w = _T414_LAST.get(key, 0) + min_s - time.time()
    if w > 0: time.sleep(w)
    _T414_LAST[key] = time.time()

def f_jtwc():
    """JTWC RSS: one item per active warning; position/winds from the warning text product."""
    _polite("jtwc")
    txt = S.get("https://www.metoc.navy.mil/jtwc/rss/jtwc.rss", headers=T248_UA, timeout=30).text
    out = []
    for name, num, issued, prod in re.findall(r"<b>\s*([A-Za-z ]+?\s+\w{3}\s*\([^)]*\))\s+Warning\s*#\s*(\d+)\s*</b>.*?Issued at (\d{2}/\d{4})Z.*?href='(https[:]//www\.metoc\.navy\.mil/jtwc/products/\w+web\.txt)'", txt, re.S):
        name = re.sub(r"\s+", " ", name).strip()
        lat = lon = None; wind = None; t = S.now()
        try:
            _polite("jtwc", 1.5)
            w = S.get(prod, headers=T248_UA, timeout=30).text
            m = re.search(r"(\d{6})Z --- NEAR (\d+\.\d)([NS]) (\d+\.\d)([EW])", w)
            if m:
                lat = float(m.group(2)) * (1 if m.group(3) == "N" else -1); lon = float(m.group(4)) * (1 if m.group(5) == "E" else -1)
                d = S.now(); t = d.replace(day=int(m.group(1)[:2]), hour=int(m.group(1)[2:4]), minute=int(m.group(1)[4:6]), second=0, microsecond=0)
                if t > d + timedelta(hours=1): t = (t.replace(day=1) - timedelta(days=1)).replace(day=int(m.group(1)[:2]))
            mw = re.search(r"MAX SUSTAINED WINDS - (\d+) KT", w); wind = int(mw.group(1)) if mw else None
        except Exception: pass
        base = 25 + (20 if wind and wind >= 64 else 0) + (15 if wind and wind >= 113 else 0)
        sid = re.search(r"(\w{3})\s*\(", name).group(1)
        title = f"JTWC: {name.title().replace('(', '(').strip()} warning #{int(num)}" + (f", max winds {wind} kt" if wind else "")
        out.append(S.item("JTWC", "JTWC", f"{sid}-{t.year}", title, "natural disaster", prod, t, lat, lon,
                          "West Pacific / Indian Ocean", base, extra={"storm": name, "warning_no": int(num), "max_wind_kt": wind}))
    return out

def f_afad():
    """AFAD (Turkey) earthquake API, M>=4.0, last 3 days (Turkey + neighbours). Family AFAD."""
    _polite("afad")
    st = (S.now() - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S"); en = (S.now() + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
    j = S.get(f"https://servisnet.afad.gov.tr/apigateway/deprem/apiv2/event/filter?start={st}&end={en}&minmag=4.0&format=json&orderby=timedesc",
              headers=T248_UA, timeout=30).json()
    out = []
    for e in j:
        try: m = float(e["magnitude"]); lat = float(e["latitude"]); lon = float(e["longitude"])
        except Exception: continue
        if m < 4.0: continue
        place = (e.get("location") or "").strip()
        prov = e.get("province"); loc = ", ".join(x for x in (e.get("district"), prov, e.get("country") or ("Türkiye" if prov else None)) if x) or place
        t = S.parse_t(e["date"] + "Z")   # AFAD API dates are UTC
        out.append(S.item("AFAD Türkiye", "AFAD", e["eventID"], f"AFAD: M{m:.1f} earthquake {place}", "natural disaster",
                          f"https://deprem.afad.gov.tr/event-detail/{e['eventID']}", t, lat, lon, loc, _small_quake_base(m),
                          extra={"mag": m, "magtype": e.get("type"), "depth_km": float(e.get("depth") or 0)}))
    return out

def f_pagasa():
    """PAGASA tropical cyclone bulletin page (HTML only). Emits one item per named cyclone inside the PAR; empty when none."""
    _polite("pagasa")
    h = S.get("https://bagong.pagasa.dost.gov.ph/tropical-cyclone/severe-weather-bulletin", headers=T248_UA, timeout=30).text
    if re.search(r"No Active Tropical Cyclone", h, re.I): return []
    out = []
    for kind, nm in set(re.findall(r"(Super Typhoon|Typhoon|Severe Tropical Storm|Tropical Storm|Tropical Depression)\s+[\"“]?([A-Z][A-Za-z]+)[\"”]?", S.strip(h))):
        sig = re.findall(r"(?:TCWS|Wind Signal)\s*(?:No\.?|#)\s*(\d)", h, re.I); top = max(map(int, sig)) if sig else 0
        out.append(S.item("PAGASA", "PAGASA", f"{nm.lower()}-{S.now().year}", f"PAGASA: {kind} {nm} bulletin" + (f", Wind Signal No. {top} raised" if top else ""),
                          "natural disaster", "https://bagong.pagasa.dost.gov.ph/tropical-cyclone/severe-weather-bulletin", S.now(), 12.9, 122.0,
                          "Philippines", 25 + 10 * top, extra={"max_signal": top}))
    if not out: raise RuntimeError("PAGASA: active-cyclone page but no storm name parsed (layout changed)")
    return out

def f_certfr():
    _polite("certfr")
    out = S.rss_generic("CERT-FR alerts (ANSSI)", "CERT-FR", "https://cert.cyber.gouv.fr/alerte/feed/", "cyber", 25, True, maxage_d=14,
                         force_cat=True, kwboost=r"exploit|zero|critique|critical")
    for it in out: it["location"] = it.get("location") or "France"
    return out

_UKHSA_RX = r"outbreak|case[s]? of|confirmed|mpox|measles|avian|influenza|bird flu|H5N|ebola|marburg|cholera|diphtheria|polio|pertussis|legionell|incident|warning|alert|heat|cold|lassa|novel|pandemic|anthrax|plague"
def f_ukhsa():
    """GOV.UK Atom for UKHSA: noisy (guidance, stats), so keep only outbreak/incident/alert items."""
    _polite("govuk")
    out = []
    for it in S.rss_generic("UK Health Security Agency", "UKHSA", "https://www.gov.uk/government/organisations/uk-health-security-agency.atom",
                            "disease", 15, True, force_cat=True, kwboost=r"outbreak|confirmed|case of|novel|pandemic|ebola|marburg|H5N1"):
        if re.search(_UKHSA_RX, it["title"], re.I) and not re.search(r"statistics|data|report: week|template|training|guidance on", it["title"], re.I):
            it["location"] = it.get("location") or "United Kingdom"
            if it.get("lat") is None: it["lat"], it["lon"] = 54.0, -2.5
            out.append(it)
    return out

def f_ga():
    """Geoscience Australia Earthquakes@GA 7-day WFS, M>=4.0 (Australia + region)."""
    _polite("ga")
    j = S.get("https://earthquakes.ga.gov.au/geoserver/earthquakes/wfs?service=WFS&request=getfeature&typeNames=earthquakes:earthquakes_seven_days"
              "&outputFormat=application/json&CQL_FILTER=display_flag=%27Y%27", headers=T248_UA, timeout=40).json()
    out = []
    for f in j.get("features", []):
        p = f["properties"]; m = p.get("preferred_magnitude") or p.get("magnitude") or 0
        try: m = float(m)
        except Exception: continue
        if m < 4.0: continue
        lon, lat = f["geometry"]["coordinates"][:2]
        if not (-50 <= lat <= -8 and 105 <= lon <= 160): continue   # Australia + near region only; global quakes already come from USGS/EMSC
        place = (p.get("description") or p.get("region") or "Australian region").strip()
        eid = p.get("event_id") or p.get("earthquake_id")
        t = S.parse_t((p.get("origin_time") or "").replace("Z", "") + "Z") if p.get("origin_time") else None
        out.append(S.item("Geoscience Australia", "GA", str(eid), f"Geoscience Australia: M{m:.1f} earthquake {place}", "natural disaster",
                          f"https://earthquakes.ga.gov.au/event/{eid}", t, lat, lon, place, _small_quake_base(m),
                          extra={"mag": m, "depth_km": p.get("depth")}))
    return out

# CWA serves a chain rooted in Taiwan GRCA, which certifi lacks; the OS CA bundle (still full verification) has it
_SYS_CA = "/etc/ssl/certs/ca-certificates.crt" if _os.path.exists("/etc/ssl/certs/ca-certificates.crt") else True
def _cwa_get(url):
    """Full chain + hostname verification, minus Python 3.13's extra X509_STRICT check (CWA's GRCA intermediate lacks a Subject Key Identifier)."""
    import ssl, urllib.request
    ctx = ssl.create_default_context(cafile=_SYS_CA if isinstance(_SYS_CA, str) else None)
    ctx.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)
    req = urllib.request.Request(url, headers=T248_UA)
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r: return r.read().decode("utf-8", "replace")
def f_cwa():
    """Taiwan CWA Seismological Center numbered (felt, significant) quakes from the English list; lat/lon from the detail page title."""
    _polite("cwa")
    from zoneinfo import ZoneInfo
    h = _cwa_get("https://scweb.cwa.gov.tw/en-US/Earthquake")
    rows = re.findall(r'href="(/en-us/earthquake/details/(ee(\d{14})\d*))".*?<td class="">([\d/: ]+)</td>\s*<td class="">([\d.]+)</td>\s*<td class="">([\d.]+)</td>\s*<td class="">\s*(.*?)\s*</td>', h, re.S)
    if not rows and "btnInfo" in h: raise RuntimeError("CWA: list rows not parsed (layout changed)")
    out, cache = [], _jload(_os.path.join(_HERE, "cwa_state.json"), {})
    for href, eid, stamp, _lt, mag, depth, county in rows[:15]:
        m = float(mag)
        t = datetime.strptime(stamp[:12], "%Y%m%d%H%M").replace(tzinfo=ZoneInfo("Asia/Taipei")).astimezone(timezone.utc)
        if t < S.now() - timedelta(days=S.HISTORY_D) or m < 4.0: continue
        url = "https://scweb.cwa.gov.tw" + href; ll = cache.get(eid)
        if not ll:
            try:
                _polite("cwa", 1.5)
                tt = re.search(r"([\d.]+)N ([\d.]+)E", _cwa_get(url))
                ll = cache[eid] = [float(tt.group(1)), float(tt.group(2))] if tt else [23.7, 121.0]
            except Exception: ll = [23.7, 121.0]
        county = S.strip(county)
        out.append(S.item("Taiwan CWA", "CWA", eid, f"Taiwan CWA: M{m:.1f} earthquake near {county}, Taiwan (depth {depth} km)", "natural disaster",
                          url, t, ll[0], ll[1], county + ", Taiwan", _small_quake_base(m), extra={"mag": m, "depth_km": float(depth)}))
    _jsave(_os.path.join(_HERE, "cwa_state.json"), dict(list(cache.items())[-60:]))
    return out

def f_ncscnl():
    """NCSC-NL advisories: only High-damage/High-probability (H) ratings matter; the feed title carries [x.xx] [M/H]."""
    _polite("ncscnl")
    out = []
    for it in S.rss_generic("NCSC-NL advisories", "NCSC-NL", "https://advisories.ncsc.nl/rss/advisories", "cyber", 8, True, force_cat=True,
                            kwboost=r"\[H/H\]|actively exploit|zero-day"):
        if re.search(r"\[H/H\]|\[M/H\]|\[H/M\]", it["title"]): it["base"] += 10
        it["location"] = it.get("location") or "Netherlands"; out.append(it)
    return out

def f_hkcert():
    _polite("hkcert")
    out = []
    for it in S.rss_generic("HKCERT security bulletins", "HKCERT", "https://www.hkcert.org/getrss/security-bulletin", "cyber", 8, True, force_cat=True,
                            kwboost=r"extreme risk|high risk|actively exploit|zero-day|in the wild"):
        it["location"] = it.get("location") or "Hong Kong"; out.append(it)
    return out

T414_SOURCES = [
    ("JTWC tropical cyclone warnings (RSS + warning text)", "https://www.metoc.navy.mil/jtwc/rss/jtwc.rss", f_jtwc),
    ("AFAD Türkiye earthquakes (API, M4+)", "https://deprem.afad.gov.tr/last-earthquakes", f_afad),
    ("PAGASA Philippines tropical cyclone bulletin", "https://bagong.pagasa.dost.gov.ph/tropical-cyclone/severe-weather-bulletin", f_pagasa),
    ("CERT-FR (ANSSI) critical alerts RSS", "https://cert.cyber.gouv.fr/alerte/feed/", f_certfr),
    ("UKHSA GOV.UK Atom (outbreaks/incidents only)", "https://www.gov.uk/government/organisations/uk-health-security-agency.atom", f_ukhsa),
    ("Geoscience Australia earthquakes (7-day WFS, M4+)", "https://earthquakes.ga.gov.au/", f_ga),
    ("Taiwan CWA Seismological Center (numbered quakes, M4+)", "https://scweb.cwa.gov.tw/en-US/Earthquake", f_cwa),
    ("NCSC-NL security advisories RSS", "https://advisories.ncsc.nl/rss/advisories", f_ncscnl),
    ("HKCERT security bulletins RSS", "https://www.hkcert.org/getrss/security-bulletin", f_hkcert),
]

# ---- t414b (2026-11-01 2:26 PM ET): second approved batch (SPC, CDC travel notices, Copernicus EMS, WOAH, InciWeb) ----
def f_spc():
    _polite("spc")
    out = []
    for it in S.rss_generic("NOAA SPC products", "NOAA-SPC", "https://www.spc.noaa.gov/products/spcrss.xml", "natural disaster", 10, True, maxage_d=2,
                            force_cat=True, kwboost=r"tornado watch|high risk|moderate risk|PDS|particularly dangerous"):
        if re.search(r"Watch|Outlook|Mesoscale|Fire Weather", it["title"], re.I) and not re.search(r"No watches are valid", it["title"], re.I):
            it["location"] = it.get("location") or "United States"; out.append(it)
    return out
def f_cdctravel():
    _polite("cdc")
    return S.rss_generic("CDC travel health notices", "CDC", "https://wwwnc.cdc.gov/travel/rss/notices.xml", "disease", 15, True, maxage_d=30,
                         force_cat=True, kwboost=r"level 3|level 4|avoid nonessential|outbreak|ebola|marburg")
def f_cems():
    """Copernicus EMS rapid mapping activations (open or updated in the last 7 days)."""
    _polite("cems")
    j = S.get("https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations-info/?limit=20", headers=T248_UA, timeout=30).json()
    out = []
    for a in j.get("results", []):
        t = S.parse_t((a.get("eventTime") or a.get("activationTime") or "") + "Z"); lu = S.parse_t((a.get("lastUpdate") or "")[:19] + "Z")
        if (lu or t) and (lu or t) < S.now() - timedelta(days=S.HISTORY_D): continue
        m = re.search(r"POINT \((-?[\d.]+) (-?[\d.]+)\)", a.get("centroid") or ""); lon, lat = (float(m.group(1)), float(m.group(2))) if m else (None, None)
        cat = "natural disaster" if re.search(r"flood|fire|storm|earthquake|volcan|landslide|cyclone|drought|tsunami|wind", a.get("category") or a.get("name") or "", re.I) else S.classify(a.get("name", ""), "natural disaster")
        out.append(S.item("Copernicus EMS", "CEMS", a["code"], f"Copernicus EMS {a['code']}: {a.get('name')}" + (" (closed)" if a.get("closed") else ""), cat,
                          f"https://rapidmapping.emergency.copernicus.eu/{a['code']}/", t, lat, lon, ", ".join(a.get("countries") or []),
                          20 if not a.get("closed") else 10, extra={"activation": a.get("activationTime"), "category": a.get("category")}))
    return out
def f_woah():
    _polite("woah")
    out = []
    for it in S.rss_generic("WOAH (World Organisation for Animal Health)", "WOAH", "https://www.woah.org/en/feed/", "disease", 10, True, maxage_d=14,
                            force_cat=True, kwboost=r"avian influenza|H5N1|outbreak|african swine fever|foot and mouth|rabies|emergency"):
        if re.search(r"influenza|outbreak|disease|fever|virus|epidemic|zoonos|H5N|rabies|swine|anthrax|alert|emergency", it["title"] + " " + json.loads(it["extra"] or "{}").get("desc", "") if isinstance(it.get("extra"), str) else it["title"], re.I):
            out.append(it)
    return out
def f_inciweb():
    """InciWeb incidents RSS, wildfires only: keep items whose text says 'type of incident is Wildfire'; prescribed burns / Rx units dropped."""
    _polite("inciweb")
    raw = S.get("https://inciweb.wildfire.gov/incidents/rss.xml", headers=T248_UA, timeout=30).content
    out = []
    for e in S.rss_items(raw):
        t = S.parse_t(e.get("pubDate"))
        if t and t < S.now() - timedelta(days=7): continue
        title = S.strip(e.get("title")); desc = S.strip(e.get("description"))
        if not re.search(r"type of incident is Wildfire", desc, re.I) or re.search(r"prescribed|\bRx\b|pile burn", title, re.I): continue
        b = 15 + (20 if re.search(r"evacuat|red flag|0% contain", desc, re.I) else 0)
        st = re.search(r"\b(Alabama|Alaska|Arizona|Arkansas|California|Colorado|Florida|Georgia|Hawaii|Idaho|Kansas|Montana|Nebraska|Nevada|New Mexico|North Carolina|Oklahoma|Oregon|South Dakota|Tennessee|Texas|Utah|Virginia|Washington|Wyoming|Minnesota|Michigan|Kentucky|Missouri)\b", desc)
        out.append(S.item("InciWeb wildfires", "InciWeb", e.get("guid") or e.get("link") or title, f"InciWeb: {title} wildfire", "natural disaster",
                          e.get("link") or "https://inciweb.wildfire.gov/", t, None, None, (st.group(1) + ", US") if st else "United States", b,
                          extra={"desc": desc[:400]}))
    return out
T414B_SOURCES = [
    ("NOAA SPC watches/outlooks RSS", "https://www.spc.noaa.gov/products/spcrss.xml", f_spc),
    ("CDC travel health notices RSS", "https://wwwnc.cdc.gov/travel/notices", f_cdctravel),
    ("Copernicus EMS rapid mapping activations", "https://rapidmapping.emergency.copernicus.eu/", f_cems),
    ("WOAH news feed (animal disease)", "https://www.woah.org/en/feed/", f_woah),
    ("InciWeb wildfires RSS (prescribed burns excluded)", "https://inciweb.wildfire.gov/incidents/rss.xml", f_inciweb),
]

EXT_SOURCES = [
    ("Reddit public RSS (multireddit: " + ", ".join(SUBS) + ")", "https://www.reddit.com/r/worldnews+news/new/.rss", f_reddit),
    ("Bluesky public search API", "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts", f_bluesky),
    ("Mastodon public hashtag timelines (mastodon.social)", "https://mastodon.social/tags/breaking", f_mastodon),
    ("YouTube live search (results page, live filter)", "https://www.youtube.com/results?search_query=breaking+news+live&sp=EgJAAQ%253D%253D", f_youtube_live),
    ("Google News RSS search (political, financial, religious, UAP, conflict, disease)", "https://news.google.com/rss/search", f_google_news),
    ("GDELT DOC 2.0 (artlist + keyword surge timelines)", "https://api.gdeltproject.org/api/v2/doc/doc", f_gdelt),
    ("Federal Reserve press releases RSS", "https://www.federalreserve.gov/feeds/press_all.xml", f_fed),
    ("SEC press releases RSS", "https://www.sec.gov/news/pressreleases.rss", f_sec),
    ("FDIC failed banks API", "https://banks.data.fdic.gov/api/failures", f_fdic),
    ("State Dept travel advisories RSS (Level 3-4)", "https://travel.state.gov/_res/rss/TAsTWs.xml", f_state),
    ("DHS NTAS alerts XML", "https://www.dhs.gov/ntas/1.1/alerts.xml", f_ntas),
    ("JMA earthquake + tsunami lists (bosai JSON)", "https://www.jma.go.jp/bosai/quake/data/list.json", f_jma),
    ("GeoNet NZ felt quakes (MMI>=3) + volcanic alert levels", "https://api.geonet.org.nz/quake?MMI=3", f_geonet),
    ("Icelandic Met Office API (VONA aviation colour codes, VALS, M3+ quakes)", "https://api.vedur.is/volcanoes/vona", f_imo),
    ("Africa CDC RSS (news + disease outbreaks)", "https://africacdc.org/news-item/feed/", f_africacdc),
    ("UK NCSC all-content RSS", "https://www.ncsc.gov.uk/api/1/services/v1/all-rss-feed.xml", f_ncsc),
    ("CERT-EU security advisories RSS", "https://cert.europa.eu/publications/security-advisories-rss", f_certeu),
    ("JPCERT/CC English alerts RSS", "https://www.jpcert.or.jp/english/rss/jpcert-en.rdf", f_jpcert),
    ("Canadian Centre for Cyber Security alerts & advisories RSS", "https://www.cyber.gc.ca/api/cccs/rss/v1/get?feed=alerts_advisories&lang=en", f_cccs),
    ("CSN Chile latest quakes (sismologia.cl table, M4+)", "https://www.sismologia.cl/", f_csn),
    ("EMSC earthquakes (seismicportal.eu FDSN event, M4.5+)", "https://www.seismicportal.eu/fdsnws/event/1/query", f_emsc),
    ("GFZ GEOFON earthquake bulletin RSS (M4.5+)", "https://geofon.gfz.de/eqinfo/list.php?fmt=rss", f_geofon),
    ("INGV earthquakes (FDSN event, M3+)", "https://webservices.ingv.it/fdsnws/event/1/query", f_ingv),
    ("USGS HANS elevated volcanoes (level changes only)", "https://volcanoes.usgs.gov/hans-public/api/volcano/getElevatedVolcanoes", f_hans),
    ("IODA internet outages (country + region, filtered)", "https://api.ioda.inetintel.cc.gatech.edu/v2/outages/events", f_ioda),
    ("MeteoAlarm warnings (EUMETNET CAP, Severe/Extreme only)", "https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-{country}", f_meteoalarm),
]
EXT_SOURCES += T414_SOURCES + T414B_SOURCES
EXT_FAILED = [
    ("ReliefWeb API v2", "https://apidoc.reliefweb.int/", "2026-11-01 t414: HTTP 403 'not using an approved appname' (v1 is 410 decommissioned); needs an appname request to ReliefWeb (form, not done). ReliefWeb still covered by the Disasters RSS in scanner.py"),
    ("Africa CDC site-wide RSS", "https://africacdc.org/feed/", "HTTP 200 but empty (no items) - news-item and disease-outbreak feeds used instead"),
    ("Icelandic Met Office site RSS", "https://en.vedur.is/rss.xml", "HTTP 200 but empty - api.vedur.is JSON used instead"),
    ("YouTube channel RSS feeds (feeds/videos.xml)", "https://www.youtube.com/feeds/videos.xml?channel_id=UCNye-wNBqNL5ZzHSJj3l8Bg", "HTTP 404 for every channel tested (Al Jazeera, Sky News, DW, Reuters, WION) - using live search instead"),
    ("Reddit JSON API", "https://www.reddit.com/r/worldnews/new.json", "HTTP 403; per-sub RSS hits 429 - one combined multireddit RSS request used instead"),
    ("Bluesky public.api.bsky.app", "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts", "HTTP 403 - api.bsky.app used instead"),
    ("US Treasury press release feed", "https://home.treasury.gov/news/press-releases/feed", "HTTP 404 (also /rss and OFAC recent-actions RSS) - Treasury/sanctions covered via Google News"),
    ("AARO news (aaro.mil)", "https://www.aaro.mil/News/", "HTTP 403 to this box; RSS endpoint returns empty - AARO covered via Google News/GDELT queries"),
    ("Telegram @WarMonitor3", "https://t.me/s/WarMonitor3", "302 - web preview disabled"),
    ("Discord analyst servers", "https://discord.com/", "No public no-login read access - not used"),
    ("X (Twitter)", "https://x.com/", "Not reachable by the scanner; the hourly chat check runs X searches and feeds results via ingest_external.py"),
    ("CENAPRED Mexico (Popocatépetl report)", "https://www.cenapred.unam.mx/", "2026-10-31 t225: home page is a Radware bot-challenge shell (no content to scripts), report URLs 404, no RSS/JSON; not bypassed - Popocatépetl still covered via GDACS/NASA EONET/news"),
]
