"""/midterms hub (seo/batch-2, Nov 1, 2026): a small, strictly neutral, server-rendered page for the 2026 U.S. midterm elections.
Every figure comes from midterms.py's synced data (midterms.db, built on the box from Wikipedia, published race ratings and official
state feeds), attributed to its source. Nothing is projected, predicted or invented; prediction-market prices are deliberately left
out of this page. Detail lives in expandable panels; outside sources are secondary links below the detail (new tab, rel=noopener).
GA4: each panel is <details data-bn-expand> and the site loader sends 'expand' {content_category, item} only when GA is allowed."""
import os, re, json, time, sqlite3, html
from datetime import datetime
import site_page as S
import midterms as M

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
PATH = "/midterms"
TITLE = "2026 midterm elections results and updates"
H1 = "2026 Midterm Elections: Results and Updates"
DESC = ("The 2026 U.S. midterm elections on Tuesday, November 3: every Senate and governor race with published ratings, "
        "poll closing times, balance of power and official state results links. Neutral and sourced.")
WHERE_TO_VOTE = [("Vote.gov: register, check your registration and find your state's voting rules", "https://vote.gov/"),
                 ("USA.gov: find your state or local election office", "https://www.usa.gov/election-office"),
                 ("Can I Vote (National Association of Secretaries of State): polling place and ID rules", "https://www.nass.org/can-I-vote")]
WIRE_RE = re.compile(r"\b(midterms?|election day|ballots?|polling (place|station)s?|voters?|voting|election (results|officials?))\b", re.I)
_C = {}
CSS = """
.mh-sec{margin:22px 0}.mh-sec>h2{font-size:20px;margin:0 0 10px}
.mh-kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:10px 0}
.mh-kv div{border:1px solid var(--bd,#2a3140);border-radius:10px;padding:10px 12px}.mh-kv b{display:block;font-size:20px}
.mh-kv span{font-size:13px}
details.mh{border:1px solid var(--bd,#2a3140);border-radius:10px;margin:8px 0;background:var(--pn,transparent)}
details.mh>summary{cursor:pointer;list-style:none;padding:12px 40px 12px 14px;min-height:44px;box-sizing:border-box;position:relative;font-weight:600}
details.mh>summary::-webkit-details-marker{display:none}
details.mh>summary:after{content:"+";position:absolute;right:14px;top:10px;font-size:20px;opacity:.7}
details.mh[open]>summary:after{content:"−"}
details.mh>summary small{display:block;font-weight:400;margin-top:2px}
details.mh .mh-b{padding:0 14px 12px}
.mh-t{width:100%;border-collapse:collapse;font-size:14px;margin:6px 0}.mh-t th,.mh-t td{text-align:left;padding:6px 4px;border-bottom:1px solid var(--bd,#2a3140);vertical-align:top}
.mh-src{font-size:13px;margin-top:10px}.mh-src a{word-break:break-word}
.mh-tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
.mh-ctl{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 10px}.mh-ctl button{min-height:40px;padding:0 14px;border-radius:8px;border:1px solid var(--bd,#2a3140);background:none;color:inherit;font:inherit;cursor:pointer}
.mh-list{padding-left:18px}.mh-list li{margin:6px 0}
"""
CTL_JS = """<script>(function(){document.querySelectorAll('[data-mh-all]').forEach(function(b){b.hidden=false;b.addEventListener('click',function(){
var g=document.getElementById(b.getAttribute('data-mh-all')),o=b.getAttribute('data-open')==='1';if(!g)return;
g.querySelectorAll('details.mh').forEach(function(d){if(o&&!d.open)d.setAttribute('data-bn-bulk','');d.open=o});
if(o&&window.bnTrack)window.bnTrack('expand',{content_category:g.id.replace(/_g$/,''),item:'all'})})})})();</script>"""

def _et(iso_s, fmt="%a, %b %-d, %-I:%M %p ET"):
    try: return datetime.fromisoformat(str(iso_s).replace("Z", "+00:00")).astimezone(M.ET).strftime(fmt)
    except Exception: return ""

def _ext(url, label):
    return f'<a href="{E(url)}" target="_blank" rel="noopener">{E(label)}</a>' if re.match(r"^https?://", str(url or "")) else ""

def _wire_items():
    out = []
    try:
        c = sqlite3.connect(f"file:{os.path.join(M.BASE, 'blackout.db')}?mode=ro", uri=True, timeout=5)
        rows = c.execute("SELECT cluster_id, title, rank, category, updated FROM clusters WHERE watchlist=0 AND COALESCE(rank,0)>=3 "
                         "AND category='political' AND updated>=datetime('now','-14 days') ORDER BY updated DESC LIMIT 400").fetchall(); c.close()
        for cid, t, rk, cat, up in rows:
            if WIRE_RE.search(t or "") and re.match(r"^[0-9a-f]{16}$", cid or ""):
                out.append({"url": f"/wire/{cid}", "title": S.clean_title(t)[:140], "meta": f"Rank {int(rk or 0)}/10 · {_et(up, '%b %-d')}"})
            if len(out) >= 8: break
    except Exception: pass
    try:
        import social
        for s in social.stories(public_only=True):
            if WIRE_RE.search((s.get("title") or "") + " " + " ".join(s.get("tags") or [])) and s.get("slug"):
                out.append({"url": f"/story/{s['slug']}", "title": (s.get("title") or "")[:140], "meta": "Video story"})
    except Exception: pass
    return out[:12]

def _rating_rows(r, meta):
    names = {m["key"]: m["name"] for m in meta or []}
    rows = "".join(f'<tr><td>{E(names.get(k, k))}</td><td>{E(v.get("t"))}</td><td>{E(v.get("date") or "")}</td></tr>'
                   for k, v in (r.get("ratings") or {}).items() if isinstance(v, dict) and v.get("t"))
    return (f'<div class="mh-tw"><table class="mh-t"><thead><tr><th>Rater</th><th>Rating</th><th>As of</th></tr></thead><tbody>{rows}</tbody></table></div>'
            if rows else "<p>No published ratings recorded for this race.</p>")

def _race(r, b, office):
    st = r.get("state") or ""; lab = r.get("label") or r.get("state_name") or st
    con = r.get("consensus") or {}
    sub = (f'Published ratings: {E(con.get("t"))} (Cook · Inside Elections · Sabato average, {int(con.get("n") or 0)} of 3 rated)' if con.get("t") else "No published ratings")
    if r.get("poll_close"):
        _f = M.POLL_CLOSE_FIRST.get(st) if r.get("district") in (None, "", 0) else None
        if _f and _f != r["poll_close"]:
            z1, z2, part = M.POLL_CLOSE_ZONES.get(st, ("", "", "most"))
            sub += ' · ' + E(f'Polls close {_et(_f, "%-I:%M %p ET")} in {part} of {r.get("state_name") or lab} ({z1} time), '
                             f'{_et(r["poll_close"], "%-I:%M %p ET")} in the {z2}-time area')
        else: sub += f' · Polls close {E(_et(r["poll_close"], "%-I:%M %p ET"))}'
    winners = [c["name"] for c in r.get("candidates") or [] if c.get("winner")]
    cands = "".join(f'<li>{E(c.get("name"))} ({E(c.get("party") or "party not listed")}){" · incumbent" if c.get("incumbent") else ""}'
                    f'{" · <b>winner (as recorded by Wikipedia editors)</b>" if c.get("winner") else ""}'
                    f'{" · " + E(c["pct"]) + "%" if c.get("pct") is not None else ""}</li>' for c in r.get("candidates") or [])
    inc = ", ".join(f'{E(i.get("name"))} ({E(i.get("party"))})' for i in r.get("incumbents") or [])
    body = (f'<p><b>Status:</b> {E(r.get("status") or "not recorded")}' + (f' · <b>Incumbent:</b> {inc}' if inc else "")
            + (f' · <b>Cook PVI:</b> {E(r["pvi"])}' if r.get("pvi") else "") + '</p>'
            + (f'<p><b>Recorded winner:</b> {E(", ".join(winners))}</p>' if winners else "")
            + (f'<p><b>Candidates on the ballot</b></p><ul class="mh-list">{cands}</ul>' if cands else "")
            + '<p><b>Published race ratings</b></p>' + _rating_rows(r, (b.get("ratings_meta") or {}).get(office))
            + '<p class="mh-src">Sources: ' + " · ".join(x for x in (_ext(r.get("article"), "Wikipedia race article"),
                                                                     _ext(M.OFFICIAL_LINKS.get(st), f"{r.get('state_name') or st} official election results")) if x)
            + '</p>')
    return (f'<details class="mh" data-bn-expand data-cat="{E(office)}" data-item="{E(r.get("id") or lab)}"><summary>{E(lab)}<small>{sub}</small></summary>'
            f'<div class="mh-b">{body}</div></details>')

def _balance(b):
    bal = b.get("balance") or {}; out = []
    for key, name, field in (("senate", "Senate", "Current seats"), ("house", "House", "Current seats"), ("governor", "Governors", "Seats before")):
        parts = [f'{E(p)} {E(v.get(field))}' for p, v in (bal.get(key) or {}).items() if isinstance(v, dict) and v.get(field)]
        if parts: out.append(f'<div><b>{name}</b><span>{" · ".join(parts)}</span></div>')
    return out

def render():
    code, b = M.summary()
    if code != 200: b = {}
    races = sorted(b.get("races") or [], key=lambda r: (r.get("state_name") or r.get("state") or "", r.get("label") or ""))
    sen = [r for r in races if r.get("office") == "senate"]; gov = [r for r in races if r.get("office") == "governor"]
    cnt = b.get("counts") or {}
    house = [r for r in b.get("house") or [] if re.search(r"toss|lean|tilt", str((r.get("consensus") or {}).get("t") or ""), re.I)]
    house.sort(key=lambda r: (r.get("state") or "", r.get("district") or 0))
    built = _et(b.get("built")) if b.get("built") else ""
    fc, lc = b.get("first_close") or M.FIRST_CLOSE, b.get("last_close") or M.LAST_CLOSE
    intro = ('<p class="dek">Election Day is Tuesday, November 3, 2026. On the ballot are all 435 seats in the U.S. House of Representatives'
             + (f', {int(cnt["senate"])} U.S. Senate seats' if cnt.get("senate") else ", a third of the U.S. Senate")
             + (f' and {int(cnt["governor"])} governorships' if cnt.get("governor") else " and many governorships")
             + '. This page lists the races with their published ratings, poll closing times and links to official results. '
               'BLACKOUT.NETWORK does not rate races or project winners.</p>')
    kv = _balance(b)
    if fc and lc: kv.insert(0, f'<div><b>{E(_et(fc.get("at"), "%a %-I %p ET"))}</b><span>First polls close ({E(fc.get("where"))})</span></div>'
                               f'<div><b>{E(_et(lc.get("at"), "%a %-I %p ET"))}</b><span>Last polls close ({E(lc.get("where"))})</span></div>')
    wire = _wire_items()
    rel = ("<ul class=\"mh-list\">" + "".join(f'<li><a href="{E(w["url"])}">{E(w["title"])}</a> <span class="meta">{E(w["meta"])}</span></li>' for w in wire) + "</ul>"
           if wire else '<p>No ranked election stories on The Wire right now. The live feed is on <a href="/#wire">The Wire</a>.</p>')
    gen = b.get("generic") or {}; cols = gen.get("columns") or []
    grows = "".join('<tr><td>' + E(r.get("source")) + '</td>' + "".join(f'<td>{E((r.get("values") or {}).get(c, ""))}</td>' for c in cols)
                    + f'<td>{E(r.get("updated") or "")}</td></tr>' for r in (gen.get("rows") or [])[:8])
    def group(gid, title, items, office, note):
        if not items: return ""
        return (f'<section class="mh-sec" id="{gid}"><h2>{E(title)} ({len(items)})</h2><p class="meta">{note}</p>'
                f'<div class="mh-ctl"><button type="button" data-mh-all="{gid}_g" data-open="1" hidden>Open all</button><button type="button" data-mh-all="{gid}_g" data-open="0" hidden>Close all</button></div>'
                f'<div id="{gid}_g">' + "".join(_race(r, b, office) for r in items) + '</div></section>')
    srcs = b.get("sources") or {}
    src_links = " · ".join(_ext(v.get("permalink") or v.get("url"), v.get("title")) for v in srcs.values() if isinstance(v, dict))
    body = ('<p class="crumb"><a href="/">Home</a> › Midterms 2026</p>'
            f'<h1 class="t">{E(H1)}</h1>' + intro
            + (f'<p class="meta">Race data as of {E(built)}. Refreshed through election night.</p>' if built else '<p class="meta">Race data is syncing; check back shortly.</p>')
            + (f'<div class="mh-kv">{"".join(kv)}</div>' if kv else "")
            + '<p><a class="btn p" href="/#midterms">Open the full Midterms tab: map, polls and live results</a></p>'
            + '<section class="mh-sec" id="vote"><h2>Where and how to vote</h2><ul class="mh-list">'
            + "".join(f'<li>{_ext(u, t)}</li>' for t, u in WHERE_TO_VOTE)
            + '</ul><p class="meta">Each race panel below also links to that state\'s official election results page.</p></section>'
            + group("senate", "Senate races", sen, "senate", "Ratings are published by the named raters; the summary line averages Cook Political Report, Inside Elections and Sabato\'s Crystal Ball; each rater\'s own call is in the panel.")
            + group("governor", "Governor races", gov, "governor", "Ratings are published by the named raters; the summary line averages Cook Political Report, Inside Elections and Sabato\'s Crystal Ball; each rater\'s own call is in the panel.")
            + group("house", "Competitive House races", house, "house",
                    f'House races whose published average rating is Toss-up, Tilt or Lean. All {int(cnt.get("house") or 435)} House races are in the <a href="/#midterms">Midterms tab</a>.')
            + (f'<section class="mh-sec" id="generic"><details class="mh" data-bn-expand data-cat="polling" data-item="generic_ballot"><summary>Generic congressional ballot: polling averages<small>{len((gen.get("rows") or [])[:8])} published averages</small></summary>'
               f'<div class="mh-b"><div class="mh-tw"><table class="mh-t"><thead><tr><th>Average</th>' + "".join(f'<th>{E(c)}</th>' for c in cols)
               + f'<th>Updated</th></tr></thead><tbody>{grows}</tbody></table></div><p class="meta">Values in percent, as published by each aggregator.</p></div></details></section>' if grows else "")
            + f'<section class="mh-sec" id="related"><h2>Related coverage on BLACKOUT.NETWORK</h2>{rel}</section>'
            + '<section class="mh-sec" id="sources"><h2>Sources</h2><p class="mh-src">Race lists, candidates, ratings and polling averages are compiled from Wikipedia (CC BY-SA 4.0), '
              'which cites each rater and pollster' + (f': {src_links}' if src_links else '') + '. Poll closing times: '
            + _ext((b.get("poll_close_source") or M.POLL_CLOSE_SRC).get("url"), (b.get("poll_close_source") or M.POLL_CLOSE_SRC).get("label"))
            + '; checked against ' + _ext(M.POLL_CLOSE_NCSL["url"], M.POLL_CLOSE_NCSL["label"])
            + '. Official results come only from state election offices. Research only; always check official sources.</p></section>'
            + f'<style>{CSS}</style>' + CTL_JS)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "@id": S.SITE + PATH + "#page", "url": S.SITE + PATH, "name": H1, "description": DESC, "inLanguage": "en",
         "isPartOf": {"@id": S.SITE + "/#website"}, "publisher": {"@id": S.SITE + "/#org"}, "dateModified": b.get("built"),
         "about": {"@type": "Event", "name": "2026 United States elections", "startDate": "2026-11-03", "eventStatus": "https://schema.org/EventScheduled",
                   "location": {"@type": "Country", "name": "United States"}},
         "mainEntity": {"@type": "ItemList", "numberOfItems": len(sen) + len(gov),
                        "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": f'{"Senate" if r.get("office") == "senate" else "Governor"}: {r.get("label")}',
                                             "url": f'{S.SITE}{PATH}#{r.get("office")}'} for i, r in enumerate(sen + gov)]}},
        {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "Home", "item": S.SITE + "/"},
                                                        {"@type": "ListItem", "position": 2, "name": "Midterms 2026", "item": S.SITE + PATH}]}]}
    return S.page(TITLE, DESC, body, PATH, "midterms", jsonld=ld, og_type="website")

def handle(path):
    """-> (code, body, ctype). Cached 120 s and rebuilt when midterms.db changes."""
    try: mt = os.path.getmtime(M.DB)
    except OSError: mt = 0
    h = _C.get("p")
    if h and h[0] == mt and time.time() - h[1] < 120: return 200, h[2], "text/html; charset=utf-8"
    b = render(); _C["p"] = (mt, time.time(), b); return 200, b, "text/html; charset=utf-8"
