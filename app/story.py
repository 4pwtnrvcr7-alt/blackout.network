"""Story permalink add-on (t303): GET /wire/<cluster_id> -> one server-rendered page per scanner story.
What happened (the scanner's brief), the 0-10 rank and confidence, every report in time order with a link to the original
source, '?since=<ISO>' highlighting of reports that are new since an email went out (newsletter UPDATE links), a #follow
section, related BLACKOUT.NETWORK videos, meta description and JSON-LD. Reads blackout.db read-only
(file:blackout.db?mode=ro); never writes anything, never touches scanner.py, scoring, push.py, jets.py or config.json.
Newsletter items link here instead of to the original source."""
import os, re, json, sqlite3, time, traceback
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import site_page as S

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db")
ET = ZoneInfo("America/New_York")
CID = re.compile(r"^[0-9a-f]{16}$")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$")
TIERS = [(10, "Catastrophic"), (9, "Critical"), (8, "Severe"), (7, "Major"), (6, "Serious"), (5, "Significant"), (4, "Regional"),
         (3, "Minor regional"), (2, "Minor"), (1, "Background"), (0, "Noise")]   # t1276u: one name per rank, same as /scoring and the brief
# Three-band severity colour (site rule): red only at rank 7+, brand yellow 4-6, neutral 0-3.
COLORS = {10: "#ff3b3b", 9: "#ff3b3b", 8: "#ff3b3b", 7: "#ff3b3b", 5: "var(--bn-sev-mid,#E5E5EA)", 3: "var(--bn-sev-mid,#E5E5EA)", 0: "#8a94a3"}   # Nov 17: rank option A, no yellow
SEV_CSS = '<style>:root{--bn-sev-mid:#E5E5EA}html[data-theme="light"]{--bn-sev-mid:#3A3A3C}</style>'
_C = {}

def tier(r):
    for k, n in TIERS:
        if (r or 0) >= k: return k, n
    return 0, "Noise"

def band(r):
    """Colour band for a 0-10 rank: 7+ red, 4-6 yellow, 0-3 neutral."""
    r = int(r or 0)
    return 7 if r >= 7 else (5 if r >= 4 else 0)

def et(iso):
    try: d = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception: return iso or ""
    return d.astimezone(ET).strftime("%b %-d, %Y, %-I:%M %p ") + ("EDT" if d.astimezone(ET).dst() else "EST")

def _ro(timeout=1.0):
    """Read-only. timeout is seconds (≤1) so a locked DB cannot stall a story page."""
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=min(1.0, float(timeout))); c.row_factory = sqlite3.Row; return c

def _what(brief, title):
    m = re.search(r"WHAT:\s*(.*?)\s*(?:WHERE:|WHEN:|CONFIDENCE:|$)", brief or "", re.S)
    w = S.clean_title((m.group(1) if m else title or "").rstrip(". "))
    return re.sub(r"\s+", " ", re.sub(r"\s*\[[^\[\]]{2,200}\]", "", w)).strip().rstrip(". ") or w   # t1276u: measured values ([magnitude: 6.4; ...]) move to Key facts

def _short(t, n=65):
    """seo/batch-1: <title> text cut at a word boundary (was title[:90], which cut mid-word); the full headline stays in the H1."""
    t = re.sub(r"\s+", " ", t or "").strip()
    if len(t) <= n: return t
    c = t[:n].rsplit(" ", 1)[0].rstrip(" ,;:-–(") or t[:n]
    return c + "…"

def _desk(cid):
    """t1330u: editor-written desk story (desk_stories.py) for an id the scanner has no cluster for; (None, []) otherwise."""
    try:
        import desk_stories as DS
        return DS.cluster(cid)
    except Exception:
        return None, []

# Clusters has no `hidden` column (scanner.py schema). #217's slim SELECT asked for it,
# both queries failed, load() returned no row, and every /wire/<id> 404'd.
_LOAD_COLS = "cluster_id, title, brief, rank, location, category, watchlist, confidence, families, n_items, first_seen, updated, event_time, lat, lon, links"
_LOAD_COLS_MIN = "cluster_id, title, brief, rank, location, category, watchlist, confidence, families, n_items, first_seen, updated"

def load(cid):
    """Cluster + alerts from the DB. Never waits more than 1 s on a lock; if the alerts query fails, still returns the title and brief."""
    try: c = _ro()
    except Exception: return _desk(cid)   # no readable blackout.db: desk stories still render
    r = None
    try:
        for cols in (_LOAD_COLS, _LOAD_COLS_MIN, "*"):
            try:
                r = c.execute(f"SELECT {cols} FROM clusters WHERE cluster_id=?", (cid,)).fetchone()
            except Exception:
                r = None
            if r:
                break
        if not r:
            return _desk(cid)
        al = []
        try:
            al = c.execute("SELECT source,family,title,source_url,first_seen,official,location FROM alerts WHERE cluster_id=? ORDER BY first_seen, official DESC LIMIT 80", (cid,)).fetchall()
        except Exception:
            al = []
        cl, items = dict(r), [dict(a) for a in al]
        try:
            import story_display as SD
            cl = SD.apply(cl)
        except Exception:
            pass
        return cl, items
    finally:
        try: c.close()
        except Exception: pass

def _tt(t):
    """Report headline as shown in the timeline: hype prefix and emoji removed (SVG-only rule)."""
    try:
        import story_report as SR; return SR.txt(t) or S.clean_title(t)
    except Exception: return S.clean_title(t)

def _ic(name):
    try:
        import story_report as SR; return SR.icon(name, "sr-i") + " "
    except Exception: return ""

def videos_for(cid):
    try:
        import social
        return [s for s in social.stories(public_only=True) if cid in (s.get("cluster_ids") or [])]
    except Exception: return []

def _cut(t, n=80):
    """Push D: display headline <= ~80 chars: first sentence if short enough, else cut at a word boundary."""
    t = (t or "").strip()
    if len(t) <= n: return t
    m = re.match(r"^(.{20,%d}?[.!?])\s" % n, t)
    if m: return m.group(1).rstrip(".")
    c = t[:n].rsplit(" ", 1)[0].rstrip(",;:-—– ")
    return c + "…"

def _h1(full, what=""):
    """Nov 17 push C: short clean headline (theme._headline, display only); the full wording stays just below as the dek."""
    try:
        import theme; short = theme._headline(full)
    except Exception: short = full
    short = _cut(short)
    dek = full if short != full else (what if what and what != full else "")
    return f'<h1 class="t">{S.E(short)}</h1>' + (f'<p class="dek">{S.E(dek)}</p>' if dek else "")

def _preparing(cid):
    body = ('<p class="crumb"><a href="/wire">The Wire</a> › Story</p><h1 class="t">This story is being prepared</h1>'
            '<p class="dek">The full write-up is not ready yet. It will appear on The Wire as soon as it is.</p>')
    return 200, S.page("Story being prepared", "This BLACKOUT.NETWORK story is being prepared.", body, f"/wire/{cid}", "threat", noindex=True)

def _ensure_writeup(cid, r, al):
    """Store a free DB template immediately so a known story can be served in this request. Cards may trail."""
    try:
        import story_writer as SW
        if SW.has_writeup(cid):
            return True
        return bool(SW.package_one(cid, row=r, al=al or [], build_card_now=False))
    except Exception:
        traceback.print_exc()
        return False

def _known_row(cid):
    """Load from the site DB, then the writer source DB. Held items are still known."""
    r, al = load(cid)
    if r:
        return r, al
    try:
        import story_writer as SW
        r, al = SW.cluster(cid)
        if r:
            return r, al or []
    except Exception:
        traceback.print_exc()
    return None, []

def render(cid, since=""):
    r, al = _known_row(cid)
    if not r:
        body = ('<p class="crumb"><a href="/wire">The Wire</a> › Story</p><h1 class="t">This story is no longer on the board</h1>'
                '<p class="dek">Stories are merged or retired as reports change. The live, ranked feed is on <a href="/wire">The Wire</a>.</p>')
        return 404, S.page("Story not found", "This BLACKOUT.NETWORK story is no longer on the board.", body, f"/wire/{cid}", "threat", noindex=True)
    # Known item: generate a template now (cheap, DB-only) and serve the full page. Never 404 a held-but-known story.
    _ensure_writeup(cid, r, al)
    rank = int(r.get("rank") or 0); k, tname = tier(rank); col = COLORS[band(rank)]
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
        link = (f'<a href="{S.E(u)}" target="_blank" rel="noopener">{S.E(_tt(a.get("title"))[:220])}</a>' if re.match(r"^https?://", u)
                else S.E(_tt(a.get("title"))[:220]))
        li.append(f'<li class="{"new" if is_new else ""}"><div class="when">{"<span class=tag>NEW</span>" if is_new else ""}{S.E(et(a.get("first_seen") or ""))}</div>'
                  f'{link}<div class="src">{S.E(a.get("source") or "")}{" · official source" if a.get("official") else ""}</div></li>')
    vids = videos_for(cid)
    vhtml = ""
    if vids:
        vhtml = '<section class="card"><h2>Watch</h2>' + "".join(
            f'<p><a href="/story/{S.E(v["slug"])}">{_ic("play")}{S.E(v["title"])}</a></p>' for v in vids) + '</section>'
    try:   # growth.py (Nov 1): Short embed, locator map, headshots, share row, follow card
        import growth as G
        g_short, g_img = G.short_html(cid, title)
        g_loc = G.locator_html(r.get("lat"), r.get("lon"), r.get("location") or "")
        g_ppl = G.people_html(f"{title} {r.get('brief') or ''}")
        try:   # t1351u: photo + drawer + profile link per public figure (people.py); the old name chips stay as the fallback
            import people as PP
            pp = PP.strip_html(cid, " ".join([title or "", r.get("brief") or ""] + [a.get("title") or "" for a in al[:60]]))
            if pp: g_ppl = ""
        except Exception: pp = ""
        share_url = f"{S.SITE}/wire/{cid}?s=x"
        share_text = f"{title} (rank {rank}/10) via BLACKOUT.NETWORK"
        x_intent = None
        try:
            import x_share
            x_intent = x_share.intent_url(x_share.with_body({
                "cluster_id": cid, "title": title, "headline": title,
                "location": r.get("location") or "", "category": r.get("category") or "",
                "brief": r.get("brief") or "", "rank": rank,
                "watchlist": watch, "hidden": r.get("hidden") or 0,
            }, alerts=rows or al, extra=what))
        except Exception:
            x_intent = None
        g_share = G.share_html(share_url, share_text, "story", intent=x_intent)
        g_follow = G.follow_html()
    except Exception: g_short = g_loc = g_ppl = g_share = g_follow = pp = ""; g_img = None
    report, dek_note = "", ""
    try:   # t1276u: news report under the headline (story_report.py; precomputed notes + images, sections dropped when empty)
        import story_report as SR
        report, dek_note = SR.render(cid, r, rows, rank, tname, title, what, r.get("location") or "", officials, eff,
                                     fams, g_loc, pp)
    except Exception:
        report, dek_note = "", ""
    if not report and pp: g_ppl = pp   # no brief rendered: the people strip still shows, under the headline
    desk_story = bool(r.get("desk_story")); breakdown = ""
    if desk_story:   # t1330u: long-form breakdown and analysis under the brief
        try:
            import desk_stories as DS; breakdown = DS.sections_html(cid)
        except Exception: breakdown = ""
    upd = (f'<section class="card"><h2>What\'s new since {S.E(et(since))}</h2><p>{len(new)} new report(s), marked NEW below.</p></section>'
           if since_ok else "")
    desc = (f"{what[:150]}. Rank {rank}/10 ({tname}). {conf}. Every report linked to its source on BLACKOUT.NETWORK.")[:300]
    loc = r.get("location") or ""
    try:   # Nov 21 2026 (Matt pt1682u): readable place label, never a raw NWS zone dump
        import geo as _geo
        loc = _geo.place_label(title or "", loc) or (loc if loc.count(";") < 2 else "")
    except Exception:
        loc = loc if loc.count(";") < 2 else ""
    elec = ""
    try:   # seo/midterms-phases: election-tagged stories (midterms_hub.is_election_story) link to the /midterms hub
        import midterms_hub as MH
        import deactivated as _DA
        if not _DA.is_off("/midterms") and MH.is_election_story(r.get("category"), r.get("title")):
            elec = ('<section class="card" id="bn_midterms_rel"><h2>2026 midterm elections</h2><p><a href="/midterms">2026 midterm elections: '
                    'where to vote, poll closing times and official results by state</a></p></section>')
    except Exception: elec = ""
    body = (SEV_CSS + f'<span id="bn_story" hidden data-rank="{rank}" data-tier="{S.E(tname.lower())}" data-cat="{S.E((r.get("category") or "").lower())}"></span>'   # seo/batch-1: GA4 story_view params
            f'<p class="crumb"><a href="/wire">The Wire</a> › Story</p>'
            f'<div><span class="pill{" pill-hi" if rank >= 7 else ""}">RANK {rank}/10 · {tname.upper()}</span>'
            f'<span class="pill">{S.E((r.get("category") or "").upper())}</span>' + ('<span class="pill">WATCHLIST</span>' if watch == 1 else "") + '</div>'
            + _h1(S.clean_title(dek_note).rstrip(". ") if dek_note else title, what if not dek_note else "")
            + f'<p class="meta">{S.E(conf)} · First seen {S.E(et(r.get("first_seen") or ""))} · Updated {S.E(et(r.get("updated") or ""))}'
            + (f' · {S.E(loc)}' if loc else "") + '</p>'
            + g_ppl + g_share + upd + report + breakdown + (g_short if report else (g_short or g_loc))
            + vhtml + elec
            + '<div class="bng-inline-slot" data-src="inline_story"><p><a class="btn p" href="/newsletter?utm_source=site&amp;utm_medium=inline&amp;utm_campaign=story">Get the free 7 AM / 7 PM brief</a></p></div>'
            + '<details class="card bnt-sacc"><summary><h2>How confident are we?</h2></summary><p>'
            + S.E(f"{eff} independent source{'' if eff == 1 else 's'}" + (f", including official sources: {', '.join(officials[:6])}." if officials else ". No official source yet."))
            + (' Ranks come from published rules.</p></details>' if _scoring_off() else ' Ranks come from published rules; see <a href="/scoring">How we score</a>.</p></details>')
            + f'<details class="card bnt-sacc"><summary><h2>Timeline and sources</h2></summary><ul class="tl">{"".join(li) or "<li>No reports stored.</li>"}</ul></details>'
            + '<section class="card" id="follow" data-bnt-skip><h2>Follow this story</h2><p>Get an UPDATE in your BLACKOUT.NETWORK brief only when this story develops. '
              'Subscribers: tap “Follow this story” under the item in any brief. Not subscribed yet? <a href="/newsletter">Get the free morning/evening brief</a>.</p></section>'
              + g_follow + '<p class="meta"><a href="/wire">← Back to The Wire</a> · <a href="/scoring">How we score</a> · <a href="/newsletter">Newsletter</a></p>')
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": title[:110], "description": desc,
          "datePublished": r.get("first_seen"), "dateModified": r.get("updated"), "url": f"{S.SITE}/wire/{cid}",
          "publisher": {"@type": "NewsMediaOrganization", "@id": f"{S.SITE}/#org", "name": S.BRAND, "url": S.SITE,
                        "logo": {"@type": "ImageObject", "url": f"{S.SITE}/icons/icon-512.png", "width": 512, "height": 512}},
          "author": {"@type": "Organization", "name": S.BRAND, "url": S.SITE}, "mainEntityOfPage": f"{S.SITE}/wire/{cid}",
          "image": [g_img or f"{S.SITE}/og/home.png?v=5"], "articleSection": (r.get("category") or "News").title(),
          "isBasedOn": [a["source_url"] for a in rows[:10] if a.get("source_url")]}
    if loc: ld["contentLocation"] = {"@type": "Place", "name": loc, **({"geo": {"@type": "GeoCoordinates", "latitude": r["lat"], "longitude": r["lon"]}} if r.get("lat") is not None and r.get("lon") is not None else {})}
    ld = {"@context": "https://schema.org", "@graph": [{k: v for k, v in ld.items() if k != "@context"},
          {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "The Wire", "item": f"{S.SITE}/wire"},
                                                          {"@type": "ListItem", "position": 2, "name": title[:110], "item": f"{S.SITE}/wire/{cid}"}]}]}
    noindex = (watch != 0 or rank < 3) and not desk_story   # t1330u: desk stories are written up in full, so they stay indexable
    return 200, S.page(_short(title), desc, body, f"/wire/{cid}", "threat", noindex=noindex, jsonld=ld, image=g_img, script=bool(g_short))


def brief_page(cid):
    """Title + brief + share button from the DB only (no growth/people/report extras). Used when the full render fails."""
    r, al = _known_row(cid)
    if not r:
        body = ('<p class="crumb"><a href="/wire">The Wire</a> › Story</p><h1 class="t">This story is no longer on the board</h1>'
                '<p class="dek">Stories are merged or retired as reports change. The live, ranked feed is on <a href="/wire">The Wire</a>.</p>')
        return 404, S.page("Story not found", "This BLACKOUT.NETWORK story is no longer on the board.", body, f"/wire/{cid}", "threat", noindex=True)
    _ensure_writeup(cid, r, al)
    title = S.clean_title(r.get("title") or "Story")
    what = _what(r.get("brief"), r.get("title"))
    rank = int(r.get("rank") or 0)
    loc = r.get("location") or ""
    share = ""
    try:
        import x_share
        share = x_share.button_html(x_share.with_body({
            "cluster_id": cid, "title": title, "headline": title,
            "location": loc, "category": r.get("category") or "",
            "brief": r.get("brief") or "", "rank": rank,
            "watchlist": r.get("watchlist") or 0, "hidden": r.get("hidden") or 0,
        }, alerts=al, extra=what))
    except Exception:
        share = ""
    src = ""
    for a in (al or [])[:12]:
        url = a.get("source_url") or ""
        lab = a.get("source") or "Source"
        if str(url).startswith("http"):
            src += f'<li><a href="{S.E(url)}" rel="noopener nofollow" target="_blank">{S.E(lab)}</a></li>'
    body = (f'<p class="crumb"><a href="/wire">The Wire</a> › Story</p>{_h1(title, what)}'
            + (f'<p class="dek">{S.E(what)}</p>' if what and what != title else "")
            + (f'<p class="meta">{S.E(loc)} · Rank {rank} of 10</p>' if True else "")
            + (f'<section class="card"><h2>Sources</h2><ul>{src}</ul></section>' if src else "")
            + (f'<p class="share">{share}</p>' if share else ""))
    return 200, S.page(_short(title), what or title, body, f"/wire/{cid}", "threat")


def handle_get(path, qs, headers=None):
    # Nov 18: the Wire timeline is /wire going forward. Hide the previous listing at /wire-classic (noindex).
    # BN_WIRE_TIMELINE=0 restores the previous listing at /wire. /wire/<cluster_id> is unchanged.
    if path in ("/wire-classic", "/wire-classic/"):
        try:
            import wire_v2
            r = wire_v2.handle("/wire-classic", qs, headers=headers)
            if r: return r
        except Exception:
            import traceback; traceback.print_exc()
        import wire_page
        return wire_page.page(noindex=True)
    if path in ("/wire", "/wire/"):
        try:
            import wire_timeline
            if wire_timeline.on():
                return 200, wire_timeline.page_html(), "text/html"
        except Exception:
            import traceback; traceback.print_exc()
    try:   # Push F: Wire v2 (wire_v2.py) on /wire (flag off), /wire/<id>, /wire2/static/*; BN_WIRE_V2=0 = the pages below
        import wire_v2
        if path.startswith(wire_v2.ST + "/"):
            return wire_v2.handle_static(path) or (404, {"error": "not found"})
        r = wire_v2.handle(path, qs, headers=headers)
        if r: return r
    except Exception:
        import traceback; traceback.print_exc()
    if path in ("/wire", "/wire/"):
        import wire_page
        return wire_page.page()
    m = re.match(r"^/wire/([0-9a-f]{16})/?$", path)
    if not m: return 404, {"error": "not found"}
    since = (qs.get("since") or [""])[0][:25]
    key = (m.group(1), since)
    try: mt = os.path.getmtime(DB)
    except OSError: return 503, {"error": "warming up"}
    try:   # t1276u: a new story_reports.json (box push) refreshes cached pages too
        import story_report as SR; mt = (mt, SR.reports_mtime())
    except Exception: pass
    try:   # template / API write-ups land in story_writer.db; include its mtime so a new brief is not stuck behind the 120s page cache
        import story_writer as SW
        wp = SW.cfg()["db"]
        mt = (mt, os.path.getmtime(wp) if os.path.exists(wp) else 0)
    except Exception:
        pass
    hit = _C.get(key)
    if hit and hit[0] == mt and time.time() - hit[1] < 120: return hit[2], hit[3], "text/html"
    try:
        code, body = render(m.group(1), since)
    except Exception:
        import traceback; traceback.print_exc()
        code, body = brief_page(m.group(1))
    if len(_C) > 500: _C.clear()
    _C[key] = (mt, time.time(), code, body)
    return code, body, "text/html"

def _scoring_off():
    try:
        import deactivated
        return deactivated.is_off("/scoring")
    except Exception:
        return False
