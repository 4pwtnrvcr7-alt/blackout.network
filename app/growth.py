"""Growth + SEO add-on (Nov 1, 2026): crawl files, cross-promotion assets and story-page visuals for BLACKOUT.NETWORK.
Routes (addons.py):
  /robots.txt                 crawl rules + Sitemap line (Cloudflare prepends its managed content-signals block)
  /sitemap.xml                home, standalone pages, public /story/<slug> pages and indexable /wire/<cluster_id> story pages
  /api/growth/app.js|app.css  site-wide enhancer loaded on every full page (server.pwa_head): Wire thumbnails (Short thumbnail
                              or a Natural Earth locator), people headshots, share buttons, in-feed follow cards, footer follow
                              block, post-signup follow prompt, ?q= search deep link
  /api/growth/world.webp      2:1 locator base map (Natural Earth, public domain), built by tools/growth_assets.py
  /api/growth/data            {shorts: {cluster_id: {yt, x, title}}, figures: [...]} for the enhancer
Data: social_shorts.json (box -> Render sync, written by /workspace/launch/growth/shorts_map.py), figures_photos.json.
Reads blackout.db read-only. Never touches scanner.py, scoring, push.py, jets.py or config.json. No cookies, no trackers."""
import os, re, json, time, sqlite3, html
BASE = os.path.dirname(os.path.abspath(__file__))
ST = os.path.join(BASE, "growth_static")
SITE = "https://blackout.network"; BRAND = "BLACKOUT.NETWORK"
X_URL = "https://x.com/BlkoutNtw"; YT_URL = "https://www.youtube.com/@blkoutntw"; YT_SUB = YT_URL + "?sub_confirmation=1"
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
_C = {}

def _cached(key, ttl, fn):
    h = _C.get(key)
    if h and time.time() - h[0] < ttl: return h[1]
    v = fn(); _C[key] = (time.time(), v); return v

def _j(name, d):
    try:
        with open(os.path.join(BASE, name), encoding="utf-8") as f: return json.load(f)
    except Exception: return d

def utm(url, source, medium, campaign):
    return url + ("&" if "?" in url else "?") + f"utm_source={source}&utm_medium={medium}&utm_campaign={campaign}"

def shorts():
    d = _j("social_shorts.json", {})
    return d.get("shorts", {}) if isinstance(d, dict) else {}

def figures():
    def build():
        out = []
        for k, f in (_j("figures_photos.json", {}) or {}).items():
            if not f.get("img") or not f.get("name"): continue
            out.append({"key": k, "name": f["name"], "img": f"/api/figures/photo/{k}.webp", "author": f.get("author") or "",
                        "license": f.get("license") or "", "source": f.get("source") or ""})
        last = {}
        for f in out: last.setdefault(f["name"].split()[-1], []).append(f)
        for f in out:   # surname alone matches only when it is unique and long enough (e.g. "Zelenskyy", "Rubio")
            s = f["name"].split()[-1]; f["alias"] = s if len(last[s]) == 1 and len(s) >= 4 else ""
        return out
    return _cached("fig", 300, build)

def people_in(text, limit=3):
    t = text or ""; hits = []
    for f in figures():
        pats = [re.escape(f["name"])] + ([r"\b" + re.escape(f["alias"]) + r"(?:'s)?\b"] if f["alias"] else [])
        m = min((x.start() for p in pats for x in [re.search(p, t)] if x), default=None)
        if m is not None: hits.append((m, f))
    return [f for _, f in sorted(hits, key=lambda h: h[0])[:limit]]

def _ro():
    c = sqlite3.connect(f"file:{os.path.join(BASE, 'blackout.db')}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row; return c

STATIC_PAGES = [("/", "hourly", "1.0"), ("/newsletter", "daily", "0.9"), ("/scoring", "weekly", "0.8"), ("/social", "hourly", "0.8"),
                ("/sources", "daily", "0.7"), ("/stats", "hourly", "0.6"), ("/midterms", "hourly", "0.7"), ("/crime", "hourly", "0.8"), ("/network", "hourly", "0.8"),
                ("/network/aws", "hourly", "0.7"), ("/network/azure", "hourly", "0.7"), ("/network/m365", "hourly", "0.7"), ("/network/gcp", "hourly", "0.7"),
                ("/network/workspace", "hourly", "0.7"), ("/network/cloudflare", "hourly", "0.7"), ("/network/akamai", "hourly", "0.7"), ("/newsletter/sample", "daily", "0.5"),
                ("/guides/bushcraft.html", "monthly", "0.5"), ("/guides/medical.html", "monthly", "0.5"),
                ("/privacy", "yearly", "0.2"), ("/tos", "yearly", "0.2")]

def sitemap():
    def build():
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        pages = STATIC_PAGES + ([("/stats", "daily", "0.4")] if os.path.exists(os.path.join(BASE, "stats.py")) else [])
        u = [(SITE + p, now if f in ("hourly", "daily") else None, f, pr) for p, f, pr in pages]
        try:
            import social
            for s in social.stories(public_only=True):
                if s.get("slug"): u.append((f"{SITE}/story/{s['slug']}", s.get("publish_at"), "weekly", "0.7"))
        except Exception: pass
        try:
            c = _ro()
            try:   # same rule as story.py: watchlist stories and rank < 3 are noindex, so they stay out of the sitemap
                rows = c.execute("SELECT cluster_id, updated FROM clusters WHERE watchlist=0 AND COALESCE(rank,0)>=3 AND updated>=? "
                                 "ORDER BY rank DESC, updated DESC LIMIT 2000", (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 30 * 86400)),)).fetchall()
            finally: c.close()
            for r in rows: u.append((f"{SITE}/wire/{r['cluster_id']}", r["updated"], "hourly", "0.6"))
        except Exception: pass
        x = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for loc, lm, f, pr in u:
            x.append(f"<url><loc>{E(loc)}</loc>" + (f"<lastmod>{E(lm)}</lastmod>" if lm else "") + f"<changefreq>{f}</changefreq><priority>{pr}</priority></url>")
        x.append("</urlset>")
        return "\n".join(x).encode()
    v = _cached("sm", 600, build)
    if b"/wire/" not in v and _C.get("sm") and _C["sm"][0] > time.time() - 30: _C["sm"] = (time.time() - 570, v)   # data not synced yet: retry in ~30 s
    return v

ROBOTS = f"""User-agent: *
Allow: /
Disallow: /internal/
Disallow: /api/reports/
Disallow: /newsletter/confirm
Disallow: /newsletter/manage
Disallow: /newsletter/unsubscribe
Disallow: /report-status
Disallow: /alerts/

Sitemap: {SITE}/sitemap.xml
"""

# ---------- server-rendered extras for /wire/<cluster_id> story pages (story.py) ----------
def locator_html(lat, lon, label=""):
    try: lat, lon = float(lat), float(lon)
    except Exception: return ""
    x = (lon + 180) / 360; y = (90 - lat) / 180
    return (f'<figure class="bng-loc bng-loc-lg" style="--fx:{x:.4f};--fy:{y:.4f}" role="img" aria-label="Locator map: {E(label or "event location")}">'
            f'<span class="bng-map"></span><span class="bng-dot"></span><figcaption>{E(label)}<small>Map: Natural Earth (public domain)</small></figcaption></figure>')

def share_html(url, text, campaign="story"):
    from urllib.parse import quote
    u = utm(url, "x", "social", campaign)
    intent = f"https://x.com/intent/post?text={quote(text[:200])}&url={quote(u)}&via=BlkoutNtw"
    return (f'<div class="bng-share" data-url="{E(url)}" data-text="{E(text[:200])}"><span class="bng-share-l">Share</span>'
            f'<a class="bng-sb" href="{E(intent)}" target="_blank" rel="noopener">Post on X</a>'
            f'<button type="button" class="bng-sb bng-copy">Copy link</button><button type="button" class="bng-sb bng-native" hidden>Share…</button></div>')

def people_html(text):
    ps = people_in(text)
    if not ps: return ""
    return ('<div class="bng-people" aria-label="People in this story">' + "".join(
        f'<a class="bng-person" href="/#figures" title="{E(p["name"])} · Photo: {E(p["author"])}, {E(p["license"])}">'
        f'<img src="{E(p["img"])}" alt="{E(p["name"])}" width="32" height="32" loading="lazy" decoding="async" onerror="this.style.visibility=\'hidden\'"><span>{E(p["name"])}</span></a>' for p in ps) + '</div>')

def short_html(cid, title):
    s = shorts().get(cid)
    if not s or not re.match(r"^[\w-]{11}$", s.get("yt") or ""): return "", None
    y = s["yt"]
    h = (f'<section class="card"><h2>Watch the 60-second Short</h2><div class="vid bng-short"><img src="https://i.ytimg.com/vi/{y}/hqdefault.jpg" alt="{E(title)}: BLACKOUT.NETWORK Short" loading="lazy">'
         f'<button type="button" data-yt="{y}" aria-label="Play: {E(title)}"><span class="play"></span></button><span class="note">YouTube · @blkoutntw</span></div>'
         f'<div class="btns"><a class="btn p" href="https://www.youtube.com/shorts/{y}" target="_blank" rel="noopener">Watch on YouTube</a>'
         + (f'<a class="btn" href="{E(s["x"])}" target="_blank" rel="noopener">See it on X</a>' if (s.get("x") or "").startswith("https://x.com/") else "")
         + f'<a class="btn" href="{YT_SUB}" target="_blank" rel="noopener">Subscribe</a></div></section>')
    return h, f"https://i.ytimg.com/vi/{y}/hqdefault.jpg"

def follow_html():
    return ('<section class="card bng-follow-card" id="bng_follow"><h2>Follow BLACKOUT.NETWORK</h2><p>Ranked, sourced alerts as they happen. The full address is '
            '<b>blackout.network</b> (no .com).</p><div class="btns">'
            f'<a class="btn p" href="/newsletter">Get the free brief</a><a class="btn" href="{X_URL}" target="_blank" rel="noopener">Follow @BlkoutNtw on X</a>'
            f'<a class="btn" href="{YT_SUB}" target="_blank" rel="noopener">Subscribe on YouTube</a></div></section>')

def org_ld():
    return {"@type": "NewsMediaOrganization", "@id": SITE + "/#org", "name": BRAND, "alternateName": ["Blackout Network", "blackout.network"], "url": SITE + "/",
            "logo": {"@type": "ImageObject", "url": SITE + "/icons/icon-512.png", "width": 512, "height": 512},
            "image": SITE + "/icons/icon-og-1200x630.png", "slogan": "Signal over noise.", "email": "hello@blackout.network",
            "sameAs": [X_URL, YT_URL], "address": {"@type": "PostalAddress", "postOfficeBoxNumber": "1228", "addressLocality": "Lake Mary",
            "addressRegion": "FL", "postalCode": "32746", "addressCountry": "US"}}

def home_ld():
    return {"@context": "https://schema.org", "@graph": [org_ld(), {"@type": "WebSite", "@id": SITE + "/#website", "url": SITE + "/", "name": BRAND,
            "description": "Independent, sourced early-warning signals on US and global threats: threat alerts and breaking news, updated around the clock. Not official alerts.",
            "publisher": {"@id": SITE + "/#org"}, "inLanguage": "en",
            "potentialAction": {"@type": "SearchAction", "target": {"@type": "EntryPoint", "urlTemplate": SITE + "/?q={search_term_string}"},
                                "query-input": "required name=search_term_string"}}]}

def home_ld_tag():
    return ('<script type="application/ld+json">' + json.dumps(home_ld(), ensure_ascii=False).replace("</", "<\\/") + "</script>").encode()

def _file(name, ctype):
    with open(os.path.join(ST, name), "rb") as f: return 200, f.read(), ctype

def handle_get(path, qs):
    if path == "/robots.txt": return 200, ROBOTS.encode(), "text/plain; charset=utf-8"
    if path == "/sitemap.xml": return 200, sitemap(), "application/xml; charset=utf-8"
    if path == "/api/growth/app.js": return _file("app.js", "application/javascript; charset=utf-8")
    if path == "/api/growth/app.css": return _file("app.css", "text/css; charset=utf-8")
    if path == "/api/growth/world.webp": return _file("world.webp", "image/webp")
    if path == "/api/growth/data":
        return 200, {"shorts": shorts(), "figures": [{k: f[k] for k in ("name", "alias", "img", "author", "license")} for f in figures()],
                     "links": {"x": X_URL, "youtube": YT_URL, "youtube_sub": YT_SUB, "newsletter": SITE + "/newsletter"}}
    return 404, {"error": "not found"}
