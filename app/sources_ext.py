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
]
EXT_FAILED = [
    ("YouTube channel RSS feeds (feeds/videos.xml)", "https://www.youtube.com/feeds/videos.xml?channel_id=UCNye-wNBqNL5ZzHSJj3l8Bg", "HTTP 404 for every channel tested (Al Jazeera, Sky News, DW, Reuters, WION) - using live search instead"),
    ("Reddit JSON API", "https://www.reddit.com/r/worldnews/new.json", "HTTP 403; per-sub RSS hits 429 - one combined multireddit RSS request used instead"),
    ("Bluesky public.api.bsky.app", "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts", "HTTP 403 - api.bsky.app used instead"),
    ("US Treasury press release feed", "https://home.treasury.gov/news/press-releases/feed", "HTTP 404 (also /rss and OFAC recent-actions RSS) - Treasury/sanctions covered via Google News"),
    ("AARO news (aaro.mil)", "https://www.aaro.mil/News/", "HTTP 403 to this box; RSS endpoint returns empty - AARO covered via Google News/GDELT queries"),
    ("Telegram @WarMonitor3", "https://t.me/s/WarMonitor3", "302 - web preview disabled"),
    ("Discord analyst servers", "https://discord.com/", "No public no-login read access - not used"),
    ("X (Twitter)", "https://x.com/", "Not reachable by the scanner; the hourly chat check runs X searches and feeds results via ingest_external.py"),
]
