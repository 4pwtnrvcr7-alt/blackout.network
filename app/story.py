"""Story permalink add-on (t303): GET /wire/<cluster_id> -> one server-rendered page per scanner story.
What happened (the scanner's brief), the 0-10 rank and confidence, every report in time order with a link to the original
source, '?since=<ISO>' highlighting of reports that are new since an email went out (newsletter UPDATE links), a #follow
section, related BLACKOUT.NETWORK videos, meta description and JSON-LD. Reads blackout.db read-only
(file:blackout.db?mode=ro); never writes anything, never touches scanner.py, scoring, push.py, jets.py or config.json.
Newsletter items link here instead of to the original source."""
import os, re, json, sqlite3, time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import site_page as S

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db")
ET = ZoneInfo("America/New_York")
CID = re.compile(r"^[0-9a-f]{16}$")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$")
TIERS = [(9, "Critical"), (7, "Major"), (5, "Significant"), (3, "Moderate"), (0, "Low")]
COLORS = {9: "#ff3b3b", 7: "#ff7a1a", 5: "#f5a524", 3: "#4aa3ff", 0: "#8a94a3"}
_C = {}

def tier(r):
    for k, n in TIERS:
        if (r or 0) >= k: return k, n
    return 0, "Low"

def et(iso):
    try: d = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception: return iso or ""
    return d.astimezone(ET).strftime("%b %-d, %Y, %-I:%M %p ") + ("EDT" if d.astimezone(ET).dst() else "EST")

def _ro():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row; return c

def _what(brief, title):
    m = re.search(r"WHAT:\s*(.*?)\s*(?:WHERE:|WHEN:|CONFIDENCE:|$)", brief or "", re.S)
    return S.clean_title((m.group(1) if m else title or "").rstrip(". "))

def _short(t, n=65):
    """seo/batch-1: <title> text cut at a word boundary (was title[:90], which cut mid-word); the full headline stays in the H1."""
    t = re.sub(r"\s+", " ", t or "").strip()
    if len(t) <= n: return t
    c = t[:n].rsplit(" ", 1)[0].rstrip(" ,;:-–(") or t[:n]
    return c + "…"

def load(cid):
    c = _ro()
    try:
        r = c.execute("SELECT * FROM clusters WHERE cluster_id=?", (cid,)).fetchone()
        if not r: return None, []
        al = c.execute("SELECT source,family,title,source_url,first_seen,official,location FROM alerts WHERE cluster_id=? ORDER BY first_seen, official DESC LIMIT 400", (cid,)).fetchall()
        return dict(r), [dict(a) for a in al]
    finally: c.close()

def videos_for(cid):
    try:
        import social
        return [s for s in social.stories(public_only=True) if cid in (s.get("cluster_ids") or [])]
    except Exception: return []

def render(cid, since=""):
    r, al = load(cid)
    if not r:
        body = ('<p class="crumb"><a href="/#wire">The Wire</a> › Story</p><h1 class="t">This story is no longer on the board</h1>'
                '<p class="dek">Stories are merged or retired as reports change. The live, ranked feed is on <a href="/#wire">The Wire</a>.</p>')
        return 404, S.page("Story not found", "This BLACKOUT.NETWORK story is no longer on the board.", body, f"/wire/{cid}", "threat", noindex=True)
    rank = int(r.get("rank") or 0); k, tname = tier(rank); col = COLORS[k]
    title = S.clean_title(r.get("title")); what = _what(r.get("brief"), r.get("title"))
    fams = [f for f in (r.get("families") or "").split(",") if f]
    eff = int(r.get("eff_families") or len(fams) or 0)
    watch = int(r.get("watchlist") or 0)
    conf = "Watchlist — unconfirmed (single source or social only)" if watch == 1 else ("Background" if watch == 2 else
           f"Confirmed by {eff} independent source{'' if eff == 1 else 's'}")
    seen = set(); rows = []
    for a in al:
        key = (a.get("source_url") or "") or (a.get("title") or "")
        if key in seen: continue
        seen.add(key); rows.append(a)
    since_ok = bool(ISO.match(since or ""))
    new = [a for a in rows if since_ok and (a.get("first_seen") or "") > since]
    officials = sorted({a["source"] for a in rows if a.get("official")})
    li = []
    for a in reversed(rows[-150:]):
        u = a.get("source_url") or ""; is_new = since_ok and (a.get("first_seen") or "") > since
        link = (f'<a href="{S.E(u)}" target="_blank" rel="noopener">{S.E(S.clean_title(a.get("title"))[:220])}</a>' if re.match(r"^https?://", u)
                else S.E(S.clean_title(a.get("title"))[:220]))
        li.append(f'<li class="{"new" if is_new else ""}"><div class="when">{"<span class=tag>NEW</span>" if is_new else ""}{S.E(et(a.get("first_seen") or ""))}</div>'
                  f'{link}<div class="src">{S.E(a.get("source") or "")}{" · official source" if a.get("official") else ""}</div></li>')
    vids = videos_for(cid)
    vhtml = ""
    if vids:
        vhtml = '<section class="card"><h2>Watch</h2>' + "".join(
            f'<p><a href="/story/{S.E(v["slug"])}">▶ {S.E(v["title"])}</a></p>' for v in vids) + '</section>'
    try:   # growth.py (Nov 1): Short embed, locator map, headshots, share row, follow card
        import growth as G
        g_short, g_img = G.short_html(cid, title)
        g_loc = G.locator_html(r.get("lat"), r.get("lon"), r.get("location") or "")
        g_ppl = G.people_html(f"{title} {r.get('brief') or ''}")
        g_share = G.share_html(f"{S.SITE}/wire/{cid}", f"{title} (rank {rank}/10) via BLACKOUT.NETWORK", "story")
        g_follow = G.follow_html()
    except Exception: g_short = g_loc = g_ppl = g_share = g_follow = ""; g_img = None
    upd = (f'<section class="card" style="border-color:#f5a524"><h2>What\'s new since {S.E(et(since))}</h2><p>{len(new)} new report(s), marked NEW below.</p></section>'
           if since_ok else "")
    desc = (f"{what[:150]}. Rank {rank}/10 ({tname}). {conf}. Every report linked to its source on BLACKOUT.NETWORK.")[:300]
    loc = r.get("location") or ""
    elec = ""
    try:   # seo/midterms-phases: election-tagged stories (midterms_hub.is_election_story) link to the /midterms hub
        import midterms_hub as MH
        if MH.is_election_story(r.get("category"), r.get("title")):
            elec = ('<section class="card" id="bn_midterms_rel"><h2>2026 midterm elections</h2><p><a href="/midterms">2026 midterm elections: '
                    'where to vote, poll closing times and official results by state</a></p></section>')
    except Exception: elec = ""
    body = (f'<span id="bn_story" hidden data-rank="{rank}" data-tier="{S.E(tname.lower())}" data-cat="{S.E((r.get("category") or "").lower())}"></span>'   # seo/batch-1: GA4 story_view params
            f'<p class="crumb"><a href="/#wire">The Wire</a> › Story</p>'
            f'<div><span class="pill" style="color:{col};border-color:{col}">RANK {rank}/10 · {tname.upper()}</span>'
            f'<span class="pill">{S.E((r.get("category") or "").upper())}</span>' + ('<span class="pill" style="color:#f5a524">WATCHLIST</span>' if watch == 1 else "") + '</div>'
            f'<h1 class="t">{S.E(title)}</h1>'
            + (f'<p class="dek">{S.E(what)}</p>' if what and what != title else "")
            + f'<p class="meta">{S.E(conf)} · First seen {S.E(et(r.get("first_seen") or ""))} · Updated {S.E(et(r.get("updated") or ""))}'
            + (f' · {S.E(loc)}' if loc else "") + '</p>'
            + g_ppl + g_share + (g_short or g_loc)
            + upd + vhtml + elec
            + '<div class="bng-inline-slot" data-src="inline_story"><p><a class="btn p" href="/newsletter?utm_source=site&amp;utm_medium=inline&amp;utm_campaign=story">Get the free 7 AM / 7 PM brief</a></p></div>'
            + '<section class="card"><h2>How confident are we?</h2><p>'
            + S.E(f"{eff} independent source{'' if eff == 1 else 's'}" + (f", including official sources: {', '.join(officials[:6])}." if officials else ". No official source yet."))
            + ' Ranks come from published rules; see <a href="/scoring">How we score</a>.</p></section>'
            + f'<section class="card"><h2>Timeline and sources</h2><ul class="tl">{"".join(li) or "<li>No reports stored.</li>"}</ul></section>'
            + '<section class="card" id="follow"><h2>☆ Follow this story</h2><p>Get an UPDATE in your BLACKOUT.NETWORK brief only when this story develops. '
              'Subscribers: tap “Follow this story” under the item in any brief. Not subscribed yet? <a href="/newsletter">Get the free morning/evening brief</a>.</p></section>'
              + g_follow + '<p class="meta"><a href="/#wire">← Back to The Wire</a> · <a href="/scoring">How we score</a> · <a href="/social">Videos</a> · <a href="/newsletter">Newsletter</a></p>')
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": title[:110], "description": desc,
          "datePublished": r.get("first_seen"), "dateModified": r.get("updated"), "url": f"{S.SITE}/wire/{cid}",
          "publisher": {"@type": "NewsMediaOrganization", "@id": f"{S.SITE}/#org", "name": S.BRAND, "url": S.SITE,
                        "logo": {"@type": "ImageObject", "url": f"{S.SITE}/icons/icon-512.png", "width": 512, "height": 512}},
          "author": {"@type": "Organization", "name": S.BRAND, "url": S.SITE}, "mainEntityOfPage": f"{S.SITE}/wire/{cid}",
          "image": [g_img or f"{S.SITE}/icons/icon-og-v2-1200x630.png"], "articleSection": (r.get("category") or "News").title(),
          "isBasedOn": [a["source_url"] for a in rows[:10] if a.get("source_url")]}
    if loc: ld["contentLocation"] = {"@type": "Place", "name": loc, **({"geo": {"@type": "GeoCoordinates", "latitude": r["lat"], "longitude": r["lon"]}} if r.get("lat") is not None and r.get("lon") is not None else {})}
    ld = {"@context": "https://schema.org", "@graph": [{k: v for k, v in ld.items() if k != "@context"},
          {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "The Wire", "item": f"{S.SITE}/#wire"},
                                                          {"@type": "ListItem", "position": 2, "name": title[:110], "item": f"{S.SITE}/wire/{cid}"}]}]}
    noindex = watch != 0 or rank < 3
    return 200, S.page(_short(title), desc, body, f"/wire/{cid}", "threat", noindex=noindex, jsonld=ld, image=g_img, script=bool(g_short))

def handle_get(path, qs):
    m = re.match(r"^/wire/([0-9a-f]{16})/?$", path)
    if not m: return 404, {"error": "not found"}
    since = (qs.get("since") or [""])[0][:25]
    key = (m.group(1), since)
    try: mt = os.path.getmtime(DB)
    except OSError: return 503, {"error": "warming up"}
    hit = _C.get(key)
    if hit and hit[0] == mt and time.time() - hit[1] < 120: return hit[2], hit[3], "text/html"
    code, body = render(m.group(1), since)
    if len(_C) > 500: _C.clear()
    _C[key] = (mt, time.time(), code, body)
    return code, body, "text/html"
