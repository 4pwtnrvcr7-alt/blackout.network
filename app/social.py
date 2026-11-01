"""Videos & posts add-on (t303/t311): the site is the hub for BLACKOUT.NETWORK's YouTube (@blkoutntw) and X (@BLKOUTNTW).
  GET /social               -> page: latest YouTube videos and X posts, each card linking back to its story page on this site.
  GET /story/<slug>         -> one story page per launch video: full sourced article, privacy-enhanced (youtube-nocookie) embed
                               loaded only on click, Watch on YouTube / X links, meta description, VideoObject JSON-LD.
  GET /api/social           -> the same data as JSON (public items only).
  GET /social/thumb/<file>  -> our own hosted thumbnails (static/social/*.jpg|png), used by newsletters (email-safe absolute URLs).
Data (all synced box -> Render as JSON, pattern social_*.json; thumbnails via static/social):
  social_stories.json   story pages: slug, title, dek, description, publish_at (UTC), youtube_id, x_url, thumb, article blocks, sources.
  social_youtube.json   box-written fallback list of PUBLIC channel uploads (tools/social_refresh.py, YouTube Data API).
  social_x_posts.json   append-only log of our own X posts, written by tools/social_xlog.py when the poster posts (no X reads).
Live YouTube RSS (channel feed) is fetched server-side at most every 30 min and cached; the box JSON is the fallback.
Launch gating: a story whose publish_at is in the future is not listed anywhere and /story/<slug> returns 404, unless the URL carries
?preview=<token> signed with the newsletter secret (purpose story_preview, bound to the slug); preview pages are noindex.
Never touches scanner.py, scoring, push.py, jets.py or config.json; reads no database."""
import os, re, json, time, threading, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import site_page as S

BASE = os.path.dirname(os.path.abspath(__file__))
THUMBS = os.path.join(BASE, "static", "social")
F_STORIES, F_YT, F_X = (os.path.join(BASE, n) for n in ("social_stories.json", "social_youtube.json", "social_x_posts.json"))
CHANNEL_ID = "UCJaUXb9_62jPv4hKzuK24Fw"
YT_URL = "https://www.youtube.com/@blkoutntw"; X_URL = "https://x.com/BLKOUTNTW"
LAUNCH = "Launching Nov 1 at 2 PM ET"
NYT = ZoneInfo("America/New_York")
SLUG = re.compile(r"^[a-z0-9][a-z0-9\-]{1,80}$")
YTID = re.compile(r"^[A-Za-z0-9_\-]{11}$")
_RSS = {"t": 0, "v": None}; _LK = threading.Lock()

def _j(p, d):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return d

def _ts(iso):
    try: return datetime.strptime(str(iso)[:19].replace(" ", "T"), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except Exception: return 0.0

def et(iso, fmt="%b %-d, %Y, %-I:%M %p"):
    t = _ts(iso)
    if not t: return ""
    d = datetime.fromtimestamp(t, NYT); return d.strftime(fmt) + (" EDT" if d.dst() else " EST")

def is_public(s, now=None): return _ts(s.get("publish_at")) <= (now or time.time())

def stories(public_only=True, now=None):
    out = []
    for s in (_j(F_STORIES, {}) or {}).get("stories") or []:
        if not isinstance(s, dict) or not SLUG.match(str(s.get("slug") or "")): continue
        if public_only and not is_public(s, now): continue
        out.append(s)
    return sorted(out, key=lambda s: (s.get("order") or 99, s.get("slug")))

def story(slug): return next((s for s in stories(False) if s.get("slug") == slug), None)

def preview_ok(tok, slug):
    try:
        import newsletter
        st, p = newsletter.read_token(tok, "story_preview")
        return st == "ok" and (p or {}).get("s") == slug
    except Exception: return False

def thumb_url(s, absolute=True):
    t = str(s.get("thumb") or "")
    if re.fullmatch(r"[A-Za-z0-9_\-]+\.(jpg|jpeg|png)", t) and os.path.isfile(os.path.join(THUMBS, t)):
        return (S.SITE if absolute else "") + "/social/thumb/" + t
    if YTID.match(str(s.get("youtube_id") or "")): return f"https://i.ytimg.com/vi/{s['youtube_id']}/hqdefault.jpg"
    return (S.SITE if absolute else "") + "/icons/icon-512.png"

def yt_watch(s): return f"https://www.youtube.com/watch?v={s['youtube_id']}" if YTID.match(str(s.get("youtube_id") or "")) else (s.get("youtube_url") or YT_URL)
def x_link(s): return s.get("x_url") or X_URL

# ---------------------------------------------------------------- YouTube: live RSS (cached), box JSON fallback
def _rss():
    with _LK:
        if _RSS["v"] is not None and time.time() - _RSS["t"] < 1800: return _RSS["v"]
        _RSS["t"] = time.time()
    vids = None
    try:
        req = urllib.request.Request(f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}", headers={"User-Agent": "Mozilla/5.0 BLACKOUT.NETWORK"})
        with urllib.request.urlopen(req, timeout=8) as r: x = r.read(600_000)
        ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "m": "http://search.yahoo.com/mrss/"}
        root = ET.fromstring(x); vids = []
        for e in root.findall("a:entry", ns)[:30]:
            vid = (e.findtext("yt:videoId", "", ns) or "").strip()
            if not YTID.match(vid): continue
            vids.append({"id": vid, "title": (e.findtext("a:title", "", ns) or "").strip(), "published": (e.findtext("a:published", "", ns) or "")[:19] + "Z",
                         "description": ((e.find("m:group", ns) or ET.Element("x")).findtext("m:description", "", ns) or "")[:400]})
    except Exception: vids = None
    with _LK: _RSS["v"] = vids if vids is not None else []
    return _RSS["v"]

def youtube():
    by = {}
    for v in (_j(F_YT, {}) or {}).get("videos") or []:
        if YTID.match(str(v.get("id") or "")) and (v.get("privacy") in (None, "public")): by[v["id"]] = v
    for v in _rss(): by[v["id"]] = {**by.get(v["id"], {}), **v}
    smap = {s.get("youtube_id"): s for s in stories(True) if s.get("youtube_id")}
    out = []
    for v in by.values():
        s = smap.get(v["id"])
        out.append({"id": v["id"], "title": (s or {}).get("title") or v.get("title") or "", "published": v.get("published") or "",
                    "url": f"https://www.youtube.com/watch?v={v['id']}", "story": f"/story/{s['slug']}" if s else None,
                    "thumb": thumb_url(s, False) if s else f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg"})
    return sorted(out, key=lambda v: v["published"], reverse=True)[:24]

def xposts():
    smap = {s["slug"]: s for s in stories(True)}; ymap = {s.get("youtube_id"): s for s in smap.values() if s.get("youtube_id")}
    out = []
    for p in (_j(F_X, {}) or {}).get("posts") or []:
        url = str(p.get("url") or "")
        if not re.match(r"^https://(x|twitter)\.com/BLKOUTNTW/status/\d{5,25}$", url, re.I): continue
        if _ts(p.get("created_at")) > time.time(): continue
        s = smap.get(p.get("story_slug")) or ymap.get(p.get("youtube_id"))
        out.append({"url": url, "text": str(p.get("text") or "")[:600], "created_at": p.get("created_at"), "story": f"/story/{s['slug']}" if s else None})
    return sorted(out, key=lambda p: p.get("created_at") or "", reverse=True)[:30]

def api():
    return {"youtube": youtube(), "x": xposts(), "stories": [{"slug": s["slug"], "title": s.get("title"), "url": f"{S.SITE}/story/{s['slug']}",
            "thumb": thumb_url(s), "youtube": yt_watch(s), "x": x_link(s), "publish_at": s.get("publish_at")} for s in stories(True)],
            "follow": {"youtube": YT_URL, "x": X_URL}}

# ---------------------------------------------------------------- pages
def _follow_btns():
    return (f'<div class="btns"><a class="btn p" href="{YT_URL}?sub_confirmation=1" target="_blank" rel="noopener me">▶ Subscribe on YouTube @blkoutntw</a>'
            f'<a class="btn" href="{X_URL}" target="_blank" rel="noopener me">Follow on X @BLKOUTNTW</a>'
            '<a class="btn" href="/newsletter">✉ Get the email brief</a></div>')

def _card(href, img, alt, title, date, btns):
    return (f'<article class="sc"><a class="th" href="{S.E(href)}"><img src="{S.E(img)}" alt="{S.E(alt)}" loading="lazy" width="480" height="270"></a>'
            f'<div class="bd"><h3><a href="{S.E(href)}">{S.E(title)}</a></h3><div class="d">{S.E(date)}</div><div class="btns">{btns}</div></div></article>')

def social_page():
    data = api(); sts = stories(True); used = set(); cards = []
    for s in sts:
        used.add(s.get("youtube_id"))
        b = (f'<a class="btn p" href="/story/{S.E(s["slug"])}">Read &amp; watch</a><a class="btn" href="{S.E(yt_watch(s))}" target="_blank" rel="noopener">YouTube</a>'
             f'<a class="btn" href="{S.E(x_link(s))}" target="_blank" rel="noopener">X</a>')
        cards.append(_card(f"/story/{s['slug']}", thumb_url(s, False), s.get("thumb_alt") or s.get("title"), s.get("title"), et(s.get("publish_at")), b))
    for v in data["youtube"]:
        if v["id"] in used: continue
        href = v["story"] or v["url"]
        b = (f'<a class="btn p" href="{S.E(v["story"])}">Read &amp; watch</a>' if v["story"] else "") + f'<a class="btn" href="{S.E(v["url"])}" target="_blank" rel="noopener">Watch on YouTube</a>'
        cards.append(_card(href, v["thumb"], v["title"], v["title"], et(v["published"]), b))
    vid = (f'<div class="grid">{"".join(cards)}</div>' if cards else
           f'<div class="card empty"><b>{LAUNCH}</b>Our first videos premiere on YouTube and X at 2:00 PM ET on Sunday, November 1, 2026. Subscribe so you don’t miss them.</div>')
    xs = "".join(f'<div class="xp"><p>{S.E(p["text"])}</p><div class="meta" style="margin:0">{S.E(et(p["created_at"]))} · '
                 f'<a href="{S.E(p["url"])}" target="_blank" rel="noopener">View on X</a>' + (f' · <a href="{S.E(p["story"])}">Read &amp; watch on BLACKOUT.NETWORK</a>' if p["story"] else "")
                 + '</div></div>' for p in data["x"])
    xs = xs or f'<div class="empty" style="padding:14px"><b>{LAUNCH}</b>Posts from <a href="{X_URL}" target="_blank" rel="noopener">@BLKOUTNTW</a> will appear here.</div>'
    body = ('<p class="crumb"><a href="/#wire">The Wire</a> › Videos &amp; posts</p><h1 class="t">Videos &amp; posts</h1>'
            '<p class="dek">BLACKOUT.NETWORK’s video reports and posts, each with a full, sourced write-up on this site.</p>' + _follow_btns() +
            f'<section style="margin-top:8px"><h2 style="font-size:19px">▶ YouTube · @blkoutntw</h2>{vid}</section>'
            f'<section class="card" style="margin-top:18px"><h2>𝕏 Latest from @BLKOUTNTW</h2>{xs}</section>')
    desc = "BLACKOUT.NETWORK videos and posts: world threat updates and explainers from YouTube @blkoutntw and X @BLKOUTNTW, each with a full sourced story page."
    return S.page("Videos & posts", desc, body, "/social", "@social", jsonld={"@context": "https://schema.org", "@type": "CollectionPage", "name": "BLACKOUT.NETWORK videos & posts", "url": S.SITE + "/social"}, og_type="website")

def story_page(s, preview=False):
    slug = s["slug"]; yid = s.get("youtube_id") if YTID.match(str(s.get("youtube_id") or "")) else None
    img = thumb_url(s, False); alt = s.get("thumb_alt") or s.get("title")
    if yid and not preview:
        player = (f'<div class="vid"><img src="{S.E(img)}" alt="{S.E(alt)}"><button type="button" data-yt="{yid}" aria-label="Play: {S.E(s.get("title"))}">'
                  '<span class="play"></span></button><span class="note">Plays from youtube-nocookie.com when you tap</span></div>')
    else:
        player = (f'<div class="vid"><img src="{S.E(img)}" alt="{S.E(alt)}"><span class="note">'
                  + ("Video premieres " + S.E(et(s.get("publish_at"))) if not is_public(s) else "Watch on YouTube or X below") + '</span></div>')
    btns = (f'<div class="btns"><a class="btn p" href="{S.E(yt_watch(s))}" target="_blank" rel="noopener">▶ Watch on YouTube</a>'
            f'<a class="btn" href="{S.E(x_link(s))}" target="_blank" rel="noopener">Watch on X</a><a class="btn" href="/newsletter">✉ Get the brief</a></div>')
    src = "".join(f'<li><a href="{S.E(x["url"])}" target="_blank" rel="noopener">{S.E(x["name"])}</a></li>' for x in s.get("sources") or [] if re.match(r"^https?://", str(x.get("url") or "")))
    rel = "".join(f'<li><a href="/wire/{S.E(c)}">Live story & every source →</a> <span class="meta">({S.E(c)})</span></li>' for c in (s.get("cluster_ids") or []) if re.fullmatch(r"[0-9a-f]{16}", str(c)))
    banner = ('<div class="card" style="border-color:#f5a524;color:#f5a524"><b>PREVIEW</b> — this page is hidden until the video premieres '
              f'({S.E(et(s.get("publish_at")))}). Not indexed; do not share.</div>') if preview else ""
    meta = " · ".join(x for x in [("Published " + et(s.get("publish_at"))) if s.get("publish_at") else "", ("Data window: " + s["data_window"]) if s.get("data_window") else ""] if x)
    body = (banner + '<p class="crumb"><a href="/#wire">The Wire</a> › <a href="/social">Videos &amp; posts</a> › Story</p>'
            f'<h1 class="t">{S.E(s.get("title"))}</h1><p class="dek">{S.E(s.get("dek") or "")}</p><p class="meta">{S.E(meta)}</p>'
            + player + btns + f'<article class="article">{S.blocks(s.get("article"))}</article>'
            + (f'<section class="card"><h2>Sources</h2><ul>{src}</ul></section>' if src else "")
            + (f'<section class="card"><h2>Follow these stories live</h2><ul>{rel}</ul></section>' if rel else "")
            + '<section class="card"><h2>Follow BLACKOUT.NETWORK</h2>' + _follow_btns() + '</section>')
    desc = (s.get("description") or s.get("dek") or S.plain(s.get("article"))[:155])[:300]
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": (s.get("title") or "")[:110], "description": desc,
          "datePublished": s.get("publish_at"), "url": f"{S.SITE}/story/{slug}", "image": [thumb_url(s)],
          "publisher": {"@type": "Organization", "name": S.BRAND, "url": S.SITE}}
    if yid:
        ld["video"] = {"@type": "VideoObject", "name": s.get("title"), "description": desc, "thumbnailUrl": [thumb_url(s)], "uploadDate": s.get("publish_at"),
                       "embedUrl": f"https://www.youtube-nocookie.com/embed/{yid}", "contentUrl": f"https://www.youtube.com/watch?v={yid}", **({"duration": s["duration"]} if s.get("duration") else {})}
    return S.page(s.get("title") or "Story", desc, body, f"/story/{slug}", "@social", noindex=preview, image=thumb_url(s), jsonld=ld, script=bool(yid and not preview))

def handle_get(path, qs):
    p = path.rstrip("/") or "/"
    if p == "/social": return 200, social_page(), "text/html"
    if p == "/api/social": return 200, api()
    m = re.match(r"^/social/thumb/([A-Za-z0-9_\-]+\.(jpg|jpeg|png))$", path)
    if m:
        f = os.path.join(THUMBS, m.group(1))
        if not os.path.isfile(f): return 404, {"error": "not found"}
        with open(f, "rb") as fh: return 200, fh.read(), "image/png" if m.group(2) == "png" else "image/jpeg"
    m = re.match(r"^/story/([a-z0-9][a-z0-9\-]{1,80})$", p)
    if m:
        s = story(m.group(1))
        if s and is_public(s): return 200, story_page(s), "text/html"
        if s and preview_ok((qs.get("preview") or [""])[0], s["slug"]): return 200, story_page(s, preview=True), "text/html"
        body = ('<h1 class="t">Story not found</h1><p class="dek">This story isn’t published yet or doesn’t exist. '
                'See <a href="/social">Videos &amp; posts</a> or <a href="/#wire">The Wire</a>.</p>')
        return 404, S.page("Story not found", "This BLACKOUT.NETWORK story is not available.", body, p, "@social", noindex=True), "text/html"
    return 404, {"error": "not found"}
