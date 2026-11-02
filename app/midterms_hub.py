"""/midterms hub (seo/batch-2, Nov 1, 2026): a small, strictly neutral, server-rendered page for the 2026 U.S. midterm elections.
Every figure comes from midterms.py's synced data (midterms.db, built on the box from Wikipedia, published race ratings and official
state feeds), attributed to its source. Nothing is projected, predicted or invented; prediction-market prices are deliberately left
out of this page. Detail lives in expandable panels; outside sources are secondary links below the detail (new tab, rel=noopener).
GA4: each panel is <details data-bn-expand> and the site loader sends 'expand' {content_category, item} only when GA is allowed."""
import os, re, json, time, sqlite3, html
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import site_page as S
import midterms as M

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
PATH = "/midterms"
NY = ZoneInfo("America/New_York")
# seo/midterms-phases (Nov 2, 2026): title, meta, H1, deck, OG and JSON-LD headline follow search intent by America/New_York time,
# computed on every request (the page cache is keyed by phase, so no phase is frozen). URL and canonical never change.
# The page shows ratings, poll closing times and links to official state results; it does not call races, so the
# results-phase copy points to official sources rather than implying BLACKOUT.NETWORK tallies or projects anything.
PHASE_B_AT = datetime(2026, 11, 3, 18, 0, tzinfo=NY)    # Tue Nov 3, 6:00 PM ET (earliest closings: Eastern-time Indiana and Kentucky)
PHASE_C_AT = datetime(2026, 11, 4, 6, 0, tzinfo=NY)     # Wed Nov 4, 6:00 AM ET
PHASES = {
    "a": {"title": "Midterm Elections 2026: Where to Vote | BLACKOUT.NETWORK",
          "desc": ("Midterm elections 2026: where do I vote, what time polls close in each state, and every Senate and governor race, "
                   "with official sources. BLACKOUT.NETWORK"),
          "h1": "2026 Midterm Elections: Where to Vote and When Polls Close",
          "deck": ("Find your polling place and your state's voting rules with the official tools below, and check when polls close. "
                   "On election night, follow results from official state election offices, linked in every race panel.")},
    "b": {"title": "Midterm Elections 2026 Results by State | BLACKOUT.NETWORK",
          "desc": ("Midterm elections 2026 results by state: links to official state results, poll closing times and every Senate "
                   "and governor race. BLACKOUT.NETWORK"),
          "h1": "2026 Midterm Election Results by State: Official Sources",
          "deck": ("Polls are closing across the country. Election results come from official state election offices; each race "
                   "panel below links to its state's official results page. BLACKOUT.NETWORK does not call races.")},
    "c": {"title": "Midterm Election Results So Far, 2026 | BLACKOUT.NETWORK",
          "desc": ("2026 midterm election results so far and when we will know the results: official state results links for every "
                   "Senate and governor race. BLACKOUT.NETWORK"),
          "h1": "2026 Midterm Election Results So Far and When We Will Know More",
          "deck": ("Counting can continue for days in some states, and official results are certified later on each state's own "
                   "schedule. Each race panel below links to its state's official results page. BLACKOUT.NETWORK does not call races.")},
}
TITLE, DESC, H1 = PHASES["a"]["title"], PHASES["a"]["desc"], PHASES["a"]["h1"]

def now_et():
    return datetime.now(NY)

def phase(now=None):
    n = (now or now_et()).astimezone(NY)
    return "a" if n < PHASE_B_AT else ("b" if n < PHASE_C_AT else "c")

def is_election_story(category, title):
    """Same rule the hub uses for its Related coverage list: scanner category 'political' plus an election term in the title."""
    return str(category or "").lower() == "political" and bool(WIRE_RE.search(title or ""))
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

def _dt(iso_s):
    try:
        d = datetime.fromisoformat(str(iso_s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception: return None

# ---------------- Phase B 'Results so far': states whose polls have closed (per request, ET clock) ----------------
# Table: app/midterms_poll_close.json (latest scheduled closing per state / per time-zone part, EST; sources cited in the file
# and on the page). A split state reads 'most of X' (or 'part of X' where the early part is small) until its last part closes.
_PCF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "midterms_poll_close.json")

def _poll_table():
    try:
        with open(_PCF, encoding="utf-8") as f: return json.load(f)
    except Exception: return None

def closed_states(now):
    t = _poll_table()
    if not t: return None, []
    out = []
    for st in t.get("states") or []:
        times = sorted(_dt(c.get("at_et")) for c in st.get("closes") or [] if _dt(c.get("at_et")))
        if not times or now < times[0]: continue
        out.append(st["name"] if now >= times[-1] else f'{st.get("early_part") or "most"} of {st["name"]}')
    return t, out

def _closed_html(now):
    t, names = closed_states(now)
    if not t or not names: return ""
    total = len(t.get("states") or []); full = sum(1 for n in names if not n.startswith(("most of ", "part of ")))
    lst = ("all states and Washington, D.C." if full == total else ", ".join(names))
    src = " · ".join(_ext(x.get("url"), x.get("label")) for x in t.get("sources") or [])
    return (f'<section class="mh-sec" id="results-so-far"><h2>Results so far</h2><p>Results come in state by state as polls close.</p>'
            f'<p><b>Polls have closed in:</b> {E(lst)}.</p>'
            f'<p class="mh-src">Scheduled poll closing times, Eastern Time: {src}. {E(t.get("note") or "")} '
            'Results for each race are on its state\'s official results page, linked in the race panels below.</p></section>')

# ---------------- Tight races (seo/midterms-phases, Nov 2) ----------------
# Data comes ONLY from the Senior Analyst's hand-off (launch/team/review/analyst/midterms_tight_races_2026-11-02/), copied
# into the repo as app/midterms_tight_races.json or app/midterms_tight_races.csv (first found wins; BN_TIGHT_RACES_FILE overrides,
# for tests). No file, an unreadable file or zero valid races -> the section is not rendered at all. Nothing is filled in:
# a rating needs rater + rating, a poll needs source + date + at least two numeric results; anything else is dropped.
# JSON: {"as_of": "...", "races": [{"id": "pa-sen", "race": "Pennsylvania Senate", "office": "Senate", "state": "PA",
#   "ratings": [{"rater", "rating", "date", "url"}], "polls": [{"source", "date", "sample", "url",
#   "results": [{"candidate", "party", "pct"}]}]}]}
# CSV (one row per rating or per poll result): race_id,race,office,state,type(rating|poll),source,date,url,rating,sample,candidate,party,pct
TIGHT_FILES = ("midterms_tight_races.json", "midterms_tight_races.csv")
_SLUG = re.compile(r"[^a-z0-9]+")

def _num(v):
    try: return float(str(v).strip().rstrip("%"))
    except Exception: return None

def _tight_load():
    import csv
    base = os.path.dirname(os.path.abspath(__file__))
    paths = [os.environ["BN_TIGHT_RACES_FILE"]] if os.environ.get("BN_TIGHT_RACES_FILE") else [os.path.join(base, f) for f in TIGHT_FILES]
    for fp in paths:
        if not os.path.isfile(fp): continue
        try:
            if fp.lower().endswith(".csv"):
                races = {}
                with open(fp, newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        row = {str(k or "").strip().lower(): str(v or "").strip() for k, v in row.items()}
                        rid = row.get("race_id") or row.get("id")
                        if not rid: continue
                        r = races.setdefault(rid, {"id": rid, "race": row.get("race"), "office": row.get("office"), "state": row.get("state"), "ratings": [], "polls": []})
                        if row.get("type") == "rating":
                            r["ratings"].append({"rater": row.get("source"), "rating": row.get("rating"), "date": row.get("date"), "url": row.get("url")})
                        elif row.get("type") == "poll":
                            key = (row.get("source"), row.get("date"), row.get("sample"))
                            pl = next((x for x in r["polls"] if x["_k"] == key), None)
                            if not pl:
                                pl = {"_k": key, "source": row.get("source"), "date": row.get("date"), "sample": row.get("sample"), "url": row.get("url"), "results": []}
                                r["polls"].append(pl)
                            pl["results"].append({"candidate": row.get("candidate"), "party": row.get("party"), "pct": row.get("pct")})
                data = {"races": list(races.values())}
            else:
                with open(fp, encoding="utf-8") as f: data = json.load(f)
                if isinstance(data, list): data = {"races": data}
            return data, os.path.getmtime(fp)
        except Exception: return None, 0
    return None, 0

def _tight_clean(data):
    out, seen = [], set()
    for r in (data or {}).get("races") or []:
        if not isinstance(r, dict): continue
        name, office, st = (str(r.get(k) or "").strip() for k in ("race", "office", "state"))
        slug = _SLUG.sub("-", str(r.get("id") or "").lower()).strip("-")
        if not (name and office and st and slug) or slug in seen: continue
        rts = [x for x in r.get("ratings") or [] if isinstance(x, dict) and str(x.get("rater") or "").strip() and str(x.get("rating") or "").strip()]
        pls = []
        for pl in r.get("polls") or []:
            if not isinstance(pl, dict) or not str(pl.get("source") or "").strip() or not str(pl.get("date") or "").strip(): continue
            res = [dict(x, pct=_num(x.get("pct"))) for x in pl.get("results") or [] if isinstance(x, dict) and str(x.get("candidate") or "").strip()]
            res = [x for x in res if x["pct"] is not None and 0 <= x["pct"] <= 100]
            if len(res) >= 2: pls.append(dict(pl, results=sorted(res, key=lambda x: str(x["candidate"]).split()[-1].lower())))
        if not (rts or pls): continue
        pls.sort(key=lambda x: str(x.get("date")), reverse=True)
        seen.add(slug); out.append({"slug": slug, "race": name, "office": office, "state": st, "ratings": rts, "polls": pls[:3]})
    return out

TIGHT_CSS = """
.tr-jump{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 12px;padding:0;list-style:none}
.tr-jump a{display:inline-flex;align-items:center;min-height:36px;padding:0 12px;border:1px solid var(--bd,#2a3140);border-radius:999px;font-size:13px;text-decoration:none;color:inherit}
.tr-jump a:hover,.tr-jump a:focus-visible{border-color:#FFC21A}
.tr-grid{display:grid;gap:12px;grid-template-columns:1fr}@media(min-width:900px){.tr-grid{grid-template-columns:1fr 1fr}}
.tr-card{border:1px solid var(--bd,#2a3140);border-top:3px solid #FFC21A;border-radius:10px;padding:12px 14px;scroll-margin-top:72px}
.tr-card:target{box-shadow:0 0 0 2px #FFC21A}
.tr-card h3{margin:0 0 2px;font-size:17px}.tr-card .tr-sub{font-size:13px;opacity:.8;margin:0 0 8px}
.tr-card h4{font-size:12px;letter-spacing:.06em;text-transform:uppercase;margin:10px 0 4px;opacity:.85}
.tr-rt{list-style:none;padding:0;margin:0;font-size:14px}.tr-rt li{display:flex;justify-content:space-between;gap:8px;padding:4px 0;border-bottom:1px solid var(--bd,#2a3140)}
.tr-poll{margin:6px 0 10px}.tr-poll .tr-src{font-size:12px;opacity:.8;margin:2px 0 4px}
.tr-row{display:grid;grid-template-columns:minmax(90px,38%) 1fr 44px;align-items:center;gap:6px;font-size:13px;margin:3px 0}
.tr-bar{height:10px;border-radius:5px;background:rgba(127,127,127,.18);overflow:hidden}
.tr-bar svg{display:block;width:100%;height:10px}
.tr-bar rect{fill:var(--bn-cat-elections,#A49589);transform-origin:left center;transform:scaleX(1);transition:transform .9s cubic-bezier(.2,.7,.2,1)}
.tr-anim .tr-bar rect{transform:scaleX(0)}.tr-anim.tr-in .tr-bar rect{transform:scaleX(1)}
.tr-mg{font-size:12px;opacity:.85}
@media (prefers-reduced-motion:reduce){.tr-bar rect{transition:none}.tr-anim .tr-bar rect{transform:scaleX(1)}}
"""
TIGHT_JS = """<script>(function(){var s=document.getElementById('tight');if(!s||!('IntersectionObserver' in window))return;
if(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches)return;var c=s.querySelectorAll('.tr-card');
c.forEach(function(e){e.classList.add('tr-anim')});var o=new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting){
x.target.classList.add('tr-in');o.unobserve(x.target)}})},{threshold:.2});c.forEach(function(e){o.observe(e)})})();</script>"""

def _tight_html():
    data, _ = _tight_load(); races = _tight_clean(data)
    if not races: return ""
    def link(u, t): return _ext(u, t) or E(t)
    cards = []
    for r in races:
        rts = "".join(f'<li><span>{link(x.get("url"), x.get("rater"))}</span><span><b>{E(x.get("rating"))}</b>'
                      + (f' · {E(x.get("date"))}' if x.get("date") else "") + '</span></li>' for x in r["ratings"])
        pls = ""
        for pl in r["polls"]:
            rows = "".join(f'<div class="tr-row"><span>{E(x["candidate"])}{" (" + E(x["party"]) + ")" if x.get("party") else ""}</span>'
                           f'<span class="tr-bar"><svg viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true"><rect x="0" y="0" height="10" width="{x["pct"]:.1f}" rx="2"/></svg></span>'
                           f'<span>{x["pct"]:g}%</span></div>' for x in pl["results"])
            top = sorted(pl["results"], key=lambda x: -x["pct"])
            mg = top[0]["pct"] - top[1]["pct"]
            mtxt = "Tied in this poll" if mg == 0 else f'Gap in this poll: {mg:.1f} points'
            pls += (f'<div class="tr-poll"><p class="tr-src">{link(pl.get("url"), pl.get("source"))} · {E(pl.get("date"))}'
                    + (f' · {E(pl.get("sample"))}' if pl.get("sample") else "") + f'</p>{rows}<p class="tr-mg">{E(mtxt)}</p></div>')
        cards.append(f'<article class="tr-card" id="race-{E(r["slug"])}"><h3>{E(r["race"])}</h3><p class="tr-sub">{E(r["office"])} · {E(r["state"])}</p>'
                     + (f'<h4>Analyst ratings</h4><ul class="tr-rt">{rts}</ul>' if rts else "")
                     + (f'<h4>Latest polls</h4>{pls}' if pls else "") + '</article>')
    jump = "".join(f'<li><a href="#race-{E(r["slug"])}">{E(r["race"])}</a></li>' for r in races)
    asof = (data or {}).get("as_of")
    return (f'<section class="mh-sec" id="tight"><h2>Tight races ({len(races)})</h2>'
            '<p class="meta">Races that published raters list as competitive. Ratings and polls are shown as published, with source and date; '
            'candidates are listed alphabetically. Polls carry a margin of error and are not predictions.' + (f' Compiled {E(asof)}.' if asof else "") + '</p>'
            f'<nav aria-label="Jump to a tight race"><ul class="tr-jump">{jump}</ul></nav><div class="tr-grid">{"".join(cards)}</div>'
            f'<style>{TIGHT_CSS}</style>{TIGHT_JS}</section>')

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

# States whose poll-close times are set county by county (Kansas, North Dakota, Oregon): every shown close time carries this caveat.
COUNTY_HOURS_VARY = {"KS", "ND", "OR"}

VOTE_GOV_TEXT = "Confirm your polling place and hours with your state election office"
VOTE_GOV_LINE = f'<p class="meta">{_ext("https://vote.gov", VOTE_GOV_TEXT)}</p>'

def _race(r, b, office):
    st = r.get("state") or ""; lab = r.get("label") or r.get("state_name") or st
    con = r.get("consensus") or {}
    sub = (f'Published ratings: {E(con.get("t"))} (Cook · Inside Elections · Sabato average, {int(con.get("n") or 0)} of 3 rated)' if con.get("t") else "No published ratings")
    if r.get("poll_close"):
        _f = M.POLL_CLOSE_FIRST.get(st) if r.get("district") in (None, "", 0) else None
        if _f and _f != r["poll_close"]:
            z1, z2, part = M.POLL_CLOSE_ZONES.get(st, ("", "", "most"))
            sub += ' · ' + E(f'Polls close {_et(_f, "%-I:%M %p ET")} in {part} of {r.get("state_name") or lab} ({z1} time), '
                             f'{_et(r["poll_close"], "%-I:%M %p ET")} in the {z2}-time area' + ('; local hours vary by county' if st in COUNTY_HOURS_VARY else ''))
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
            + (f'<p class="mh-src">Election office: {_ext(_o.get("office_url"), _o.get("office_name"))}</p>' if (_o := M.ELECTION_OFFICES.get(st) or {}) and r.get("poll_close") else "")
            + '</p>')
    return (f'<details class="mh" data-bn-expand data-cat="{E(office)}" data-item="{E(r.get("id") or lab)}"><summary>{E(lab)}<small>{sub}</small></summary>'
            f'<div class="mh-b">{body}</div></details>')

def _balance(b):
    bal = b.get("balance") or {}; out = []
    for key, name, field in (("senate", "Senate", "Current seats"), ("house", "House", "Current seats"), ("governor", "Governors", "Seats before")):
        parts = [f'{E(p)} {E(v.get(field))}' for p, v in (bal.get(key) or {}).items() if isinstance(v, dict) and v.get(field)]
        if parts: out.append(f'<div><b>{name}</b><span>{" · ".join(parts)}</span></div>')
    return out

def render(now=None):
    now = (now or now_et()).astimezone(NY); ph = phase(now); P = PHASES[ph]
    code, b = M.summary()
    if code != 200: b = {}
    races = sorted(b.get("races") or [], key=lambda r: (r.get("state_name") or r.get("state") or "", r.get("label") or ""))
    sen = [r for r in races if r.get("office") == "senate"]; gov = [r for r in races if r.get("office") == "governor"]
    cnt = b.get("counts") or {}
    house = [r for r in b.get("house") or [] if re.search(r"toss|lean|tilt", str((r.get("consensus") or {}).get("t") or ""), re.I)]
    house.sort(key=lambda r: (r.get("state") or "", r.get("district") or 0))
    built = _et(b.get("built")) if b.get("built") else ""
    fc, lc = b.get("first_close") or M.FIRST_CLOSE, b.get("last_close") or M.LAST_CLOSE
    intro = (f'<p class="dek">{E(P["deck"])}</p><p>Election Day {"was" if ph == "c" else "is"} Tuesday, November 3, 2026. On the ballot are all 435 seats in the U.S. House of Representatives'
             + (f', {int(cnt["senate"])} U.S. Senate seats' if cnt.get("senate") else ", a third of the U.S. Senate")
             + (f' and {int(cnt["governor"])} governorships' if cnt.get("governor") else " and many governorships")
             + '. This page lists the races with their published ratings, poll closing times and links to official results. '
               'BLACKOUT.NETWORK does not rate races or project winners.</p>')
    # dateModified: the later of the last race-data build and the moment this phase's copy took effect (both real, never in the future)
    mods = [d for d in (_dt(b.get("built")), PHASE_B_AT if ph != "a" else None, PHASE_C_AT if ph == "c" else None) if d]
    date_mod = max(mods).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if mods else now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
                f'<div id="{gid}_g">' + "".join(_race(r, b, office) for r in items) + '</div>' + (VOTE_GOV_LINE if any(r.get("poll_close") for r in items) else '') + '</section>')
    srcs = b.get("sources") or {}
    src_links = " · ".join(_ext(v.get("permalink") or v.get("url"), v.get("title")) for v in srcs.values() if isinstance(v, dict))
    body = ('<p class="crumb"><a href="/">Home</a> › Midterms 2026</p>'
            f'<h1 class="t">{E(P["h1"])}</h1>' + intro + (_closed_html(now) if ph == "b" else "")
            + (f'<p class="meta">Race data as of {E(built)}. Refreshed through election night.</p>' if built else '<p class="meta">Race data is syncing; check back shortly.</p>')
            + (f'<div class="mh-kv">{"".join(kv)}</div>' if kv else "")
            + '<p><a class="btn p" href="/#midterms">Open the full Midterms tab: map, polls and live results</a></p>'
            + '<section class="mh-sec" id="vote"><h2>Where and how to vote</h2><ul class="mh-list">'
            + "".join(f'<li>{_ext(u, t)}</li>' for t, u in WHERE_TO_VOTE)
            + '</ul><p class="meta">Each race panel below also links to that state\'s election office and official election results page.</p>' + VOTE_GOV_LINE + '</section>'
            + _tight_html()
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
        {"@type": "CollectionPage", "@id": S.SITE + PATH + "#page", "url": S.SITE + PATH, "name": P["h1"], "headline": P["h1"], "description": P["desc"], "inLanguage": "en",
         "isPartOf": {"@id": S.SITE + "/#website"}, "publisher": {"@id": S.SITE + "/#org"}, "dateModified": date_mod,
         "about": {"@type": "Event", "name": "2026 United States elections", "startDate": "2026-11-03", "endDate": "2026-11-03",
                   "description": "U.S. general election day, Tuesday, November 3, 2026, with all 435 U.S. House seats, a third of the U.S. Senate and many governorships on the ballot.",
                   "eventStatus": "https://schema.org/EventScheduled", "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
                   "image": [S.SITE + "/icons/icon-og-v2-1200x630.png"],
                   "location": {"@type": "Place", "name": "United States", "address": {"@type": "PostalAddress", "addressCountry": "US"}}},
         "mainEntity": {"@type": "ItemList", "numberOfItems": len(sen) + len(gov),
                        "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": f'{"Senate" if r.get("office") == "senate" else "Governor"}: {r.get("label")}',
                                             "url": f'{S.SITE}{PATH}#{r.get("office")}'} for i, r in enumerate(sen + gov)]}},
        {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "Home", "item": S.SITE + "/"},
                                                        {"@type": "ListItem", "position": 2, "name": "Midterms 2026", "item": S.SITE + PATH}]}]}
    return S.page(P["title"], P["desc"], body, PATH, "midterms", jsonld=ld, og_type="website")

def handle(path, now=None):
    """-> (code, body, ctype). Cached 120 s per phase and rebuilt when midterms.db changes or the ET phase changes."""
    try: mt = os.path.getmtime(M.DB)
    except OSError: mt = 0
    mt = (mt, _tight_load()[1]); ph = phase(now); h = _C.get("p")
    if now is None and h and h[0] == mt and h[3] == ph and time.time() - h[1] < 120: return 200, h[2], "text/html; charset=utf-8"
    b = render(now)
    if now is None: _C["p"] = (mt, time.time(), b, ph)
    return 200, b, "text/html; charset=utf-8"
