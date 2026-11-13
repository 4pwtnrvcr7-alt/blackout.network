"""BLACKOUT.NETWORK brief, layout v2 (Matt, Nov 13 2026: t1365u, round 2 t1391u): shorter, grouped, quieter.

Off by default. On with the Render env BN_NL_V2=1 (or "template": "v2" in newsletter_config.json); newsletter.render() calls
render() here and falls back to the v1 layout if anything in this module raises. Issue selection, the brief gate, the
Hamas pin / featured desk stories, the QA gate, tracking and every footer control are unchanged: this module only draws.

Layout
  * Top 3 (the subject line's order), then Featured, then the stories grouped under colour-coded category headers (War &
    conflict, Health & outbreaks, Weather & natural hazards, Politics & government, Cyber & tech, Space/SpaceX/Starlink,
    Money & markets). Groups are ordered by their highest-ranked story; inside a group, highest rank first. Category colours
    never reuse the rank band colours (red/amber/green stay rank-only).
  * Each story: one picture (rights-cleared story image, else the story page's file photo with an on-picture "FILE PHOTO ·
    place, year" label, else our own story-at-a-glance graphic), rank kicker, headline, one-sentence summary, named people with
    a right-aligned Profile link, and right-aligned text links: "Read the full brief" (our story page) first, then YouTube / X
    when our post of the story is live. No buttons.
  * Next SpaceX launch + up to two SpaceX/Starlink headlines from the SpaceX tab's own cache (spacex.db; no new API calls).
  * A preparedness tip tied to the lead category, linking an existing /ready checklist PDF and /ready.
  * Footer (13px): every image credit and outside source in one numbered list, CAN-SPAM address, controls as text links.
Email-safe: one 600px table column, inline styles, hosted JPEG/PNG only, dark plates kept in light-mode clients (v1 lock),
body text >= 16px, every link right-aligned in a >= 44px tap row, no #fragment links.
"""
import html, os, re, urllib.parse

E = lambda s: html.escape("" if s is None else str(s), quote=True)
FACE = "Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
BG, SURF, SURF2, LINE = "#0B0C0F", "#16181C", "#1C1F24", "#2A2D33"
TX, BODY, MU, AC, INK = "#F5F5F7", "#D2D2D7", "#A1A1A6", "#FFC21A", "#0B0C0F"
RED, AMBER, GREEN = "#C8102E", "#FFC21A", "#3FA66A"
RED_TX = "#FF6B6B"   # rank 7+ text on the dark card (band red, lifted for contrast)
BODY_PX, FOOT_PX = 16, 13   # Matt, Nov 13: no body text below 16px (12pt); footer >= 12px
IMG_W = 568   # card inner width at 600px
NL_PLACE_ALIAS = {r"\bhormuz\b": "strait of hormuz", r"\bgaza\b|\bwest bank\b": "state of palestine", r"\bbritain\b|\bbritish\b|\buk\b": "united kingdom"}
_YT = re.compile(r"^https://(?:www\.)?youtube\.com/(?:shorts/|watch\?v=)[A-Za-z0-9_-]{6,20}$")

def on(c=None):
    return os.environ.get("BN_NL_V2", "0") == "1" or str((c or {}).get("template") or "").lower() == "v2"

# ------------------------------------------------------------------ data helpers
def _N():
    import newsletter as N
    return N

def _base(c): return (c or {}).get("base_url", "https://blackout.network").rstrip("/")

def _reports():
    try:
        import story_report as SR
        return SR.reports() or {}
    except Exception:
        return {}

def _local_mid(src):
    """Same-origin media id for an allowlisted https image, else None (never hotlink an outside host)."""
    try:
        import people as PP
        loc = PP.media_url(src)
    except Exception:
        return None
    return loc[len("/api/media/"):] if isinstance(loc, str) and loc.startswith("/api/media/") else None

def _credit_html(im):
    cr, lic, link = (im.get("credit") or "").strip(), (im.get("license") or "").strip(), (im.get("link") or "").strip()
    cap = (im.get("caption") or "").strip()
    bits = []
    if cap: bits.append(E(cap))
    who = "Image: " + E(cr) + (f", {E(lic)}" if lic else "")
    if re.match(r"^https?://", link):
        who = f'<a href="{E(link)}" style="color:{MU};text-decoration:underline">{who}</a>'
    bits.append(who + ".")
    return " ".join(bits)

def _credit(im):
    """{"subject","year","kind","who","link"} for the footer's numbered credits list."""
    cap = str(im.get("caption") or "").strip()
    subj, yr, kind = "", "", "photo"
    m = re.match(r"^File photo of (.{2,80}?)(?: \((\d{4})\))?\.", cap) or re.match(r"^(.{2,80}?), (\d{4})\. File photo", cap)
    if m: subj, yr, kind = m.group(1), m.group(2) or "", "file photo"
    else: subj = re.sub(r"\s*Not taken at this event\.?", "", cap).strip().rstrip(".") or str(im.get("alt") or "Story picture")
    who = ", ".join(x for x in ((im.get("credit") or "").strip(), (im.get("license") or "").strip()) if x) or "credit on the story page"
    link = (im.get("link") or "").strip()
    return {"subject": subj, "year": yr, "kind": kind, "who": who, "link": link if re.match(r"^https?://", link) else ""}

def _place_pick(text):
    pl = ((_reports().get("people") or {}).get("places") or {})
    for rx, key in NL_PLACE_ALIAS.items():
        if re.search(rx, text or "", re.I) and isinstance(pl.get(key), dict) and pl[key].get("src"):
            return pl[key]
    return None

def lead_image(it, c, title=None):
    """{"src": absolute https, "alt", "credit_html", "kind": photo|file|graphic} for one story. Never None."""
    N = _N(); base = _base(c); cid = it.get("cluster_id") or ""
    for im in ((_reports().get("images") or {}).get(cid) or []):
        if not isinstance(im, dict) or not str(im.get("src") or "").startswith("https://"): continue
        mid = _local_mid(im["src"])
        if mid:
            return {"src": f"{base}/newsletter/img/lead/{mid}", "alt": im.get("alt") or im.get("caption") or "", "kind": "photo",
                    "credit_html": _credit_html(im), "credit": _credit(im)}
    head = title or N.card_headline(it)
    text = " ".join(x for x in (head, it.get("title"), (it.get("analyst") or {}).get("what")) if x)
    fb = None
    try:
        import people as PP
        fb = PP.lead_for(cid, " ".join(x for x in (head, it.get("title")) if x), it.get("where") or "", text)
    except Exception:
        fb = None
    if not (isinstance(fb, dict) and fb.get("src")):
        fb = _place_pick(" ".join(x for x in (head, it.get("title"), it.get("where")) if x))
    if isinstance(fb, dict) and fb.get("src"):
        mid = _local_mid(fb["src"])
        if mid:
            return {"src": f"{base}/newsletter/img/lead/{mid}", "alt": fb.get("alt") or fb.get("caption") or "", "kind": "file",
                    "credit_html": _credit_html(fb), "credit": _credit(fb)}
    n = int(it.get("n_items") or 0)
    built = f"built from the {n} reports on this story" if n > 1 else "built from this story's own reports"
    return {"src": f"{base}/newsletter/img/card/{cid}.png", "kind": "graphic",
            "alt": f"Story at a glance: rank {int(it.get('rank') or 0)} of 10" + (f", {it['where']}" if it.get("where") else ""),
            "credit_html": f"Graphic: {N.BRAND}, {built}. No rights-cleared photo of this event was available.", "credit": None}

def people_of(it, c, title=None, limit=3):
    """Named people with a profile: [{"slug","name","role","img","url","credit"}]. Headline order first."""
    try:
        import people as PP
    except Exception:
        return []
    N = _N(); base = _base(c)
    head = title or N.card_headline(it)
    text = " ".join(x for x in (head, it.get("title"), (it.get("analyst") or {}).get("what"), it.get("what")) if x)
    try: ps = PP.people_for(it.get("cluster_id") or "", text)
    except Exception: ps = []
    def pos(p):
        try: m = re.search(p.get("rx") or "~~", text)
        except re.error: m = None
        return m.start() if m else 10 ** 6
    out = []
    for p in sorted(ps, key=pos):
        if pos(p) >= 10 ** 6: continue   # only people this issue's text actually names
        slug = p.get("slug") or ""
        if not re.match(r"^[a-z0-9][a-z0-9-]{0,80}$", slug): continue
        po = p.get("portrait") or {}
        has_img = os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "img", "people", slug + ".webp")) \
            or bool(_local_mid(po.get("avatar_src") or po.get("src") or ""))
        cr = ""
        if has_img and po:
            cr = f'{(po.get("author") or "Unknown author").strip()} / Wikimedia Commons' + (f', {po.get("license")}' if po.get("license") else "")
        out.append({"slug": slug, "name": p.get("name") or slug, "role": p.get("role") or "", "credit_link": po.get("source") or "",
                    "img": f"{base}/newsletter/img/person/{slug}.jpg" if has_img else "", "url": f"{base}/people/{slug}", "credit": cr})
        if len(out) >= limit: break
    return out

def youtube_for(it):
    """Our own live video of this story, or None. social_links.json (posting pipeline, link-checked, topic policy) first,
    then a social_stories.json video that lists this cluster."""
    cid = it.get("cluster_id") or ""
    try:
        import home_feed as HF
        v = (HF.links() or {}).get(cid) or {}
        if v.get("yt") and _YT.match(v["yt"]) and HF.topic_ok(it.get("title") or "", ""):
            return v["yt"]
    except Exception:
        pass
    try:
        for s in _N().load_stories():
            if cid in (s.get("cluster_ids") or []) and re.match(r"^[A-Za-z0-9_-]{6,20}$", str(s.get("youtube_id") or "")):
                return f"https://www.youtube.com/watch?v={s['youtube_id']}"
    except Exception:
        pass
    return None

def summary(it, n=210, hard=280):
    """One complete sentence, never cut mid-sentence and never split on an abbreviation such as "Nov." or "St.":
    the analyst's what-happened, else the analyst's why-it-matters, else the scanner summary, else why.
    Prefers a sentence of <= n characters; if none exists, the first sentence up to `hard` characters."""
    N = _N(); head = N.card_headline(it)
    a = it.get("analyst") or {}
    note = a.get("what") if a.get("from_note") else None   # the desk analyst's own what-happened line wins over scanner text
    cands = []
    for cand in (note, (a.get("takeaway") or it.get("why")) if a.get("from_note") else None, it.get("what"), it.get("why")):
        t = re.sub(r"\s+", " ", str(cand or "")).strip()
        if not t or N._same_line(t, head): continue
        sents = [x for x in N._sentences(t) if x.strip()]
        if sents: cands.append(sents)
    def fin(x): return x if x[-1] in ".!?\u2026\"'\u201d\u2019)" else x + "."
    for sents in cands:
        if 30 <= len(sents[0]) <= n or (len(sents[0]) <= n and len(sents) == 1): return fin(sents[0])
    for sents in cands:
        if len(sents[0]) <= hard: return fin(sents[0])
    return ""

# ------------------------------------------------------------------ html pieces
def _rank_chip(it):
    if it.get("rank") is None: return ""
    rk = max(0, min(10, int(it.get("rank") or 0))); name = it.get("tier") or _N().tier(rk)[0]
    col = RED_TX if rk >= 7 else (AMBER if rk >= 4 else GREEN)
    return f'<span class="{"ta" if 4 <= rk < 7 else ""}" style="color:{col};font-weight:700">Rank {rk} · {E(name)}</span>'

def _place_named(place, it):
    text = " ".join(str(x or "") for x in (it.get("display_title"), it.get("title")))   # the headline must name it
    words = [w for w in re.findall(r"[A-Za-z\u00C0-\u024F'-]{4,}", place) if w.lower() not in ("approx", "near", "city", "region", "province", "county", "state")]
    return any(re.search(r"\b" + re.escape(w[:-1] if w.endswith("e") else w), text, re.I) for w in words) if words else False

def _kicker(it, extra=None):
    """Rank (band colour), place when the headline names it, and state flags. The category lives in the group header."""
    N = _N(); sep = f'<span class="bnm" style="color:{MU}"> · </span>'
    parts = [x for x in (_rank_chip(it),) if x]
    place = (it.get("where") or "").strip()
    if place and not _place_named(place, it): place = ""   # a scanner place the story text never names is left off (pre-publish A2)
    if place: parts.append(f'<span class="bnm" style="color:{MU}">{E(N._one_line(place, 34))}</span>')
    if it.get("update"): parts.append(f'<span class="ta" style="color:{AMBER}">Update</span>')
    elif it.get("lead") and it.get("section") == "developing": parts.append(f'<span class="bnm" style="color:{MU}">Developing</span>')
    if it.get("editorial") or it.get("section") == "watchlist": parts.append(f'<span class="ta" style="color:{AMBER}">Unconfirmed</span>')
    for x in extra or (): parts.append(x)
    if not parts: return ""
    return f'<div style="font:600 16px/22px {FACE};margin:0 0 6px 0">{sep.join(parts)}</div>'

# ------------------------------------------------------------------ round 2 (Matt, Nov 13 12:22 PM): category groups, subtle
# right-aligned text links (44px tap rows), credits and sources in one numbered footer list, SpaceX launch, preparedness tip,
# no text below 16px outside the footer (footer >= 12px).
GROUPS = {   # key: (label, accent). Accents avoid the rank band colours (red/amber/green stay reserved for rank).
    "war": ("War & conflict", "#F9A8D4"), "health": ("Health & outbreaks", "#5EEAD4"), "hazards": ("Weather & natural hazards", "#38BDF8"),
    "politics": ("Politics & government", "#A5B4FC"), "cyber": ("Cyber & tech", "#C4B5FD"), "space": ("Space, SpaceX & Starlink", "#E7E5E4"),
    "money": ("Money & markets", "#BEF264"), "world": ("More from the wire", "#94A3B8")}
_CAT_GROUP = {"war/conflict": "war", "political": "politics", "natural disaster": "hazards", "disease": "health", "cyber": "cyber",
              "space weather": "space", "financial": "money"}
_SPACE_RX = re.compile(r"\b(spacex|starlink|starship|starshield|falcon ?9|falcon heavy|crew dragon|starbase)\b", re.I)
_WAR_RX = re.compile(r"\b(missiles?|drones?|bomb(?:s|ing|ed)?|car bomb|airstrikes?|air strikes?|shelling|artillery|troops|military|"
                     r"assassinat\w*|strikes?|naval mines?|invasion|ceasefire|war)\b", re.I)
_POL_RX = re.compile(r"\b(lawmakers?|legislat\w*|parliament\w*|senate|congress\w*|election\w*|sanctions?|ministers?|president\w*|"
                     r"government|courts?|supreme court|ruling|bans? (?:on )?\w+ journalists|diplomat\w*)\b", re.I)
_HEALTH_RX = re.compile(r"\b(ebola|outbreak|virus|flu|influenza|measles|cholera|pandemic|epidemic|vaccine)\b", re.I)
_HAZ_RX = re.compile(r"\b(earthquake|quake|tsunami|hurricane|typhoon|cyclone|tornado|flood\w*|wildfire|volcan\w*|storm)\b", re.I)

def group_of(it):
    """Category group for one story: SpaceX/Starlink first, then the tracked category; a political/other scanner label on a story
    whose headline is plainly about weapons or fighting goes under War & conflict."""
    t = " ".join(str(x or "") for x in (it.get("display_title"), it.get("title"), _N().card_headline(it)))
    if _SPACE_RX.search(t): return "space"
    g = _CAT_GROUP.get((it.get("category") or "").strip().lower())
    if g in (None, "politics") and _WAR_RX.search(t): return "war"
    if g is None and _HEALTH_RX.search(t): return "health"
    if g is None and _HAZ_RX.search(t): return "hazards"
    if g is None and _POL_RX.search(t): return "politics"
    return g or "world"

def _rk(it):
    r = it.get("rank")
    return -1 if r is None else int(r)

def grouped(issue, items):
    """[(group_key, [stories])]: each group's stories by rank (highest first, analyst-notes order breaks ties), groups ordered
    by their highest-ranked story (then by the earliest notes position), so the most serious category always leads."""
    order = {cid: i for i, cid in enumerate(issue.get("notes_ids") or ())}
    pos = lambda it: order.get(it.get("cluster_id"), 10 ** 6)
    by = {}
    for it in items: by.setdefault(group_of(it), []).append(it)
    for g in by: by[g].sort(key=lambda it: (-_rk(it), pos(it)))
    return sorted(by.items(), key=lambda kv: (-max(_rk(x) for x in kv[1]), min(pos(x) for x in kv[1]), kv[0] == "world"))

class Refs:
    """The footer's numbered list of image credits and outside sources (nothing of this sits under an image or a story).
    One line per pictured subject and credit: a file photo and a headshot of the same person by the same author share a line."""
    def __init__(self): self._rows = []; self._seen = {}; self._cred = {}
    def add(self, text, link=""):
        k = ("src", text, link)
        if k not in self._seen: self._rows.append({"text": text, "link": link}); self._seen[k] = len(self._rows)
        return self._seen[k]
    def credit(self, subject, kind, who, link="", year=""):
        k = (subject.lower(), who)
        if k in self._cred:
            r = self._cred[k]
            if kind not in r["kinds"]: r["kinds"].append(kind)
            r["year"] = r["year"] or year; r["link"] = r["link"] or link
            return r["n"]
        r = {"cred": True, "subject": subject, "kinds": [kind], "who": who, "link": link, "year": year}
        self._rows.append(r); r["n"] = len(self._rows); self._cred[k] = r
        return r["n"]
    @property
    def items(self):
        out = []
        for r in self._rows:
            if r.get("cred"):
                out.append((f'{r["subject"]}{", " + r["year"] if r["year"] else ""} ({" and ".join(r["kinds"])}): {r["who"]}.', r["link"]))
            else:
                out.append((r["text"], r["link"]))
        return out

def _p(text, mt=6, col=None, cls="bnx"):
    return f'<p class="{cls}" style="margin:{mt}px 0 0 0;font:400 {BODY_PX}px/24px {FACE};color:{col or BODY};text-align:left">{text}</p>'

def _links(primary=None, secondary=()):
    """Right-aligned text links (right-thumb reach), each a 44px-tall tap row. primary=(label, url) in the accent colour."""
    a = []
    if primary:
        a.append(f'<a href="{E(primary[1])}" class="bnr" style="display:inline-block;padding:12px 0 12px 18px;font:700 {BODY_PX}px/20px {FACE};'
                 f'color:{AC};text-decoration:none">{primary[0]}&nbsp;&rarr;</a>')
    for lab, url in secondary:
        a.append(f'<a href="{E(url)}" class="bnm" style="display:inline-block;padding:12px 0 12px 18px;font:600 {BODY_PX}px/20px {FACE};'
                 f'color:{MU};text-decoration:underline">{lab}</a>')
    if not a: return ""
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td align="right" style="text-align:right;padding:2px 0 0 0">{"".join(a)}</td></tr></table>')

def _img_html(im, refs, about):
    """Picture only: no caption under it. File photos carry their archive label on the picture (newsletter_img); the credit goes
    to the footer list."""
    cr = im.get("credit")
    if cr: refs.credit(cr["subject"], cr["kind"], cr["who"], cr["link"], cr["year"])
    return (f'<img src="{E(im["src"])}" width="{IMG_W}" alt="{E(im["alt"])}" '
            f'style="display:block;width:100%;max-width:{IMG_W}px;height:auto;border:0;border-radius:12px;background:{SURF2};'
            f'color:{MU};font:400 {BODY_PX}px/22px {FACE};margin:0 0 12px 0">')

def _people_html(ps, refs):
    """Name left, "Profile" link right-aligned on the same 44px row. Headshot credits go to the footer list."""
    if not ps: return ""
    rows = []
    for p in ps:
        pic = (f'<img src="{E(p["img"])}" width="40" height="40" alt="{E(p["name"])}" style="display:block;width:40px;height:40px;'
               f'border:0;border-radius:20px;background:{SURF2}">' if p["img"] else
               f'<div style="width:40px;height:40px;border-radius:20px;background:{SURF2};color:{TX};font:700 {BODY_PX}px/40px {FACE};text-align:center">'
               f'{E("".join(w[0] for w in p["name"].split()[:2]))}</div>')
        if p.get("credit"): refs.credit(p["name"], "headshot", p["credit"], p.get("credit_link") or "")
        rows.append(f'<tr><td width="48" valign="middle" style="width:48px;padding:2px 0">{pic}</td>'
                    f'<td valign="middle" class="bnt" style="font:600 {BODY_PX}px/22px {FACE};color:{TX};text-align:left">{E(p["name"])}</td>'
                    f'<td valign="middle" align="right" style="text-align:right"><a href="{E(p["url"])}" class="bnm" '
                    f'style="display:inline-block;padding:12px 0 12px 12px;font:600 {BODY_PX}px/20px {FACE};color:{MU};text-decoration:underline">Profile</a></td></tr>')
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:10px 0 0 0;border-top:1px solid {LINE}">'
            + "".join(rows) + '</table>')

def _card(inner, accent=None):
    """One story: its own panel, a thin category-colour bar on the left, 20px of space to the next story."""
    bar = (f'<td width="4" bgcolor="{accent}" style="width:4px;background:{accent};border-radius:16px 0 0 16px;font-size:0;line-height:0">&nbsp;</td>' if accent else "")
    return (f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:10px 16px;background:{BG}">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{SURF}" class="bncard" '
            f'style="background:{SURF};border-radius:16px;border-collapse:separate"><tr>{bar}'
            f'<td class="bncard" bgcolor="{SURF}" style="padding:16px 16px 8px 16px;background:{SURF};border-radius:{"0 16px 16px 0" if accent else "16px"};color:{TX};'
            f'word-break:break-word;overflow-wrap:anywhere;text-align:left">{inner}</td></tr></table></td></tr>')

def _headline(text):
    return f'<div class="bnt bnh1" data-bn-h="1" style="font:700 21px/27px {FACE};color:{TX};text-align:left">{E(text)}</div>'

def x_for(it):
    try:
        import home_feed as HF
        v = (HF.links() or {}).get(it.get("cluster_id") or "") or {}
        return v["x"] if v.get("x") and HF.topic_ok(it.get("title") or "", "") else None
    except Exception:
        return None

def story_card(it, links, c, refs, accent=None):
    N = _N(); url = N.wire_url(it["cluster_id"], c=c); head = N.card_headline(it)
    im = lead_image(it, c); ps = people_of(it, c); yt = youtube_for(it); xu = x_for(it); u = it.get("update")
    H = [_img_html(im, refs, N._one_line(head, 60)), _kicker(it), _headline(head)]
    if u:
        bits = []
        if u.get("rank_from") is not None and u["rank_from"] != u.get("rank_to"):
            bits.append(f"Rank {'raised' if u.get('up') else 'lowered'} {u['rank_from']} to {u['rank_to']}.")
        if u.get("n_new"): bits.append(f"{u['n_new']} new report{'s' if u['n_new'] != 1 else ''}.")
        H.append(_p(f'<b class="ta" style="color:{AMBER}">What\'s new:</b> {E(" ".join(bits) or "Updated.")}', 8))
    s = summary(it)
    if s: H.append(_p(E(s), 8))
    H.append(_people_html(ps, refs))
    sec = ([("YouTube", yt)] if yt else []) + ([("X", xu)] if xu else [])
    fl = N.follow_links(links.get("_row"), it["cluster_id"], c)
    if links.get("_row") and fl.get("follow"):   # subscriber token links only; previews skip the #follow anchor
        sec.append(("Unfollow", fl["unfollow"]) if it.get("followed") and fl.get("unfollow") else ("Follow", fl["follow"]))
    H.append(_links(("Read the full brief", url), sec))
    return _card("".join(H), accent)

def featured_card(f_, c, refs):
    N = _N(); it = {"cluster_id": f_["cluster_id"], "title": f_["title"], "display_title": f_["title"], "rank": None, "where": ""}
    try:
        import desk_stories as DS
        s = DS.get(f_["cluster_id"]) or {}
        it.update(rank=s.get("rank"), where=s.get("location") or "", n_items=len(s.get("reports") or []))
    except Exception:
        pass
    im = lead_image(it, c, title=f_["title"]); ps = people_of(dict(it, what=f_.get("text")), c, title=f_["title"])
    kick = E(f_["kicker"].upper()) + ((" · " + E(f_["tag"].upper())) if f_.get("tag") else "")
    H = [_img_html(im, refs, N._one_line(f_["title"], 60)),
         f'<div style="font:700 {BODY_PX}px/22px {FACE};letter-spacing:.6px;color:#22C55E;margin:0 0 6px 0">{kick}</div>', _headline(f_["title"])]
    if f_.get("text"): H.append(_p(E(f_["text"]), 8))
    H.append(_people_html(ps, refs))
    yt = youtube_for(it); xu = x_for(it)
    H.append(_links(("Read the full brief", f_["url"]), ([("YouTube", yt)] if yt else []) + ([("X", xu)] if xu else [])))
    return _card("".join(H), accent="#22C55E")

def _group_head(label, accent, sub=None, first=False):
    return (f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:{"18" if first else "30"}px 16px 2px 16px;background:{BG}">'
            + ("" if first else f'<div style="height:1px;background:{LINE};font-size:0;line-height:1px;margin:0 0 22px 0">&nbsp;</div>')
            + f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td width="10" valign="middle" style="width:10px"><div style="width:10px;height:10px;border-radius:5px;background:{accent};font-size:0;line-height:0">&nbsp;</div></td>'
            f'<td valign="middle" style="padding:0 0 0 10px;font:700 {BODY_PX}px/22px {FACE};letter-spacing:1.2px;color:{accent}">{E(label.upper())}</td></tr></table>'
            + (f'<div class="bnm" style="font:400 {BODY_PX}px/22px {FACE};color:{MU};margin:4px 0 0 0;text-align:left">{E(sub)}</div>' if sub else "")
            + '</td></tr>')

def _line_item(title, url, meta):
    return (f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:8px 16px 0 16px;background:{BG};text-align:left">'
            f'<div class="bnt" style="font:600 {BODY_PX}px/23px {FACE};color:{TX}">{E(title)}</div>'
            f'<div class="bnm" style="font:400 {BODY_PX}px/22px {FACE};color:{MU};margin-top:2px">{meta}</div>'
            f'{_links(("Open", url))}</td></tr>')

def _notes_order(issue, items):
    """Stories in the analyst notes' order (the order of the subject line and the Top 3), the rest in the issue's order."""
    rank = {cid: i for i, cid in enumerate(issue.get("notes_ids") or ())}
    return sorted(items or [], key=lambda it: rank.get(it.get("cluster_id"), 10 ** 6))

def top_stories(issue, n=3):
    """The analyst notes' order first (the same story the subject line names), then the issue's own order."""
    N = _N(); pool = list(N._story_pool(issue))
    order = [x for x in (issue.get("notes_ids") or ())]
    rank = {cid: i for i, cid in enumerate(order)}
    pool.sort(key=lambda it: rank.get(it.get("cluster_id"), 10 ** 6))   # stable: stories without a note keep their order
    return pool[:n]


def _top3(issue, c):
    N = _N(); pool = top_stories(issue, 3)
    head = f'<div class="bnt" style="font:700 21px/27px {FACE};color:{TX};margin:0 0 2px 0;text-align:left">{N.MATTERS}</div>'
    box = lambda inner: (f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:4px 16px 8px 16px;background:{BG}">'
                         f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{SURF}" style="background:{SURF};border-radius:16px;border-collapse:separate">'
                         f'<tr><td class="bns" bgcolor="{SURF}" style="padding:16px 18px 8px 18px;background:{SURF};border-radius:16px;text-align:left">{inner}</td></tr></table></td></tr>')
    if not pool:   # quiet issue: the heading and a dashboard link only, nothing invented
        if issue.get("featured"): return ""
        return box(head + _links(("Open the live dashboard", _base(c) + "/")))
    li = "".join(f'<tr><td valign="top" class="bnt" style="padding:10px 0 0 0;font:400 {BODY_PX}px/23px {FACE};color:{TX};text-align:left">'
                 f'<b style="font-weight:700">{i}. {E(N.card_headline(it))}</b></td></tr>' for i, it in enumerate(pool, 1))
    n = len(N._story_pool(issue)) + len(issue.get("featured") or [])
    mins = max(1, round(n * 0.5))
    return box(f'<div class="bnr" style="font:700 {BODY_PX}px/22px {FACE};letter-spacing:1px;color:{AC};margin:0 0 4px 0">TOP 3 RIGHT NOW</div>{head}'
               f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{li}</table>'
               f'<div class="bnm" style="font:400 {BODY_PX}px/22px {FACE};color:{MU};margin:10px 0 8px 0">{n} stor{"y" if n == 1 else "ies"} · about {mins} min · '
               f'sections below start with the highest-ranked category</div>')

def _masthead(issue, c):
    N = _N(); lab = N.slot_label(issue["slot"]); day = issue.get("label") or issue["end"].astimezone(N.ET).strftime("%A, %B %-d, %Y")
    logo = N.logo_url("dark", c)
    return (f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:20px 16px 14px 16px;background:{BG};text-align:left">'
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td valign="middle" style="padding:0 12px 0 0"><img src="{E(logo)}" width="44" height="44" alt="BLACKOUT.NETWORK" '
            f'style="display:block;width:44px;height:44px;border:0;border-radius:10px"></td>'
            f'<td valign="middle"><div class="bnt" style="font:800 20px/24px {FACE};letter-spacing:1.2px;color:{TX}">BLACKOUT.NETWORK</div>'
            f'<div class="bnm" style="font:400 {BODY_PX}px/22px {FACE};color:{MU}">{E(N.TAGLINE)}</div></td></tr></table>'
            f'<div class="bnr" style="font:700 {BODY_PX}px/22px {FACE};letter-spacing:.8px;color:{AC};margin-top:14px">{E(lab.upper())} BRIEF · {E(day.upper())}</div>'
            '</td></tr>')

# ------------------------------------------------------------------ SpaceX / Starlink (read-only: the site's own cached data)
_DONE = {"Success", "Failure", "Partial Failure"}
_STATUS = {"Go": "Go for launch", "TBC": "Time to be confirmed", "TBD": "Date to be determined", "Hold": "On hold", "In Flight": "In flight"}
_NEWS_OK = ("reuters", "associated press", "ap news", "axios", "spacenews", "spaceflight now", "nasaspaceflight", "space.com", "cnbc", "bbc",
            "nasa", "the verge", "ars technica", "usa today", "cbs news", "abc news", "nbc news", "npr", "washington post", "new york times")

def _ts(s):
    from datetime import datetime
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

def _spacex_raw():
    """{"upcoming": [...], "news": [...]} from the SpaceX tab's own cache (spacex.db, filled by /api/spacex and refresh_all);
    never calls Launch Library or any news API itself. BN_NL_SPACEX_JSON (a saved /api/spacex reply) is for previews and tests."""
    import json, sqlite3, time
    p = os.environ.get("BN_NL_SPACEX_JSON")
    if p:
        try:
            d = json.load(open(p, encoding="utf-8"))
            return {"upcoming": ((d.get("upcoming") or {}).get("items") or []), "news": ((d.get("news") or {}).get("items") or [])}
        except Exception:
            return {}
    db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spacex.db")
    if not os.path.isfile(db): return {}
    out = {}
    try:
        k = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        for key, ttl in (("upcoming", 12 * 3600), ("news", 8 * 3600)):
            r = k.execute("SELECT ts, payload FROM cache WHERE k=?", (key,)).fetchone()
            if r and time.time() - float(r[0]) < ttl: out[key] = (json.loads(r[1]) or {}).get("items") or []
        k.close()
    except Exception:
        return {}
    return out

def spacex_block(issue):
    """{"next": {...}, "after": {...}|None, "news": [{"title","source","url"}]} or None."""
    N = _N(); raw = _spacex_raw(); at = issue["end"]
    from datetime import timedelta
    ups = []
    for x in raw.get("upcoming") or []:
        if not isinstance(x, dict) or x.get("status") in _DONE: continue
        t = _ts(x.get("win_end") or x.get("net"))
        if t and t >= at: ups.append(x)
    ups.sort(key=lambda x: str(x.get("net") or ""))
    news, seen = [], set()
    for x in raw.get("news") or []:
        t = _ts(x.get("time")); title = re.sub(r"\s+", " ", str(x.get("title") or "")).strip()
        src = str(x.get("source") or "").strip(); url = str(x.get("url") or "")
        if not (t and at - timedelta(hours=30) <= t <= at + timedelta(hours=1)): continue
        if not title or not _SPACE_RX.search(title) or not url.startswith("https://") or "http" in title.lower(): continue
        if not any(o in src.lower() for o in _NEWS_OK): continue
        title = re.sub(r"\s+[-\u2013\u2014|]\s+" + re.escape(src) + r"$", "", title)
        key = re.sub(r"\W+", " ", title.lower())[:40]
        if key in seen or len(title) > 140: continue
        seen.add(key); news.append({"title": title, "source": src, "url": url, "t": t})
    news.sort(key=lambda x: ("news.google.com" in x["url"], -x["t"].timestamp()))   # direct outlet links first, then newest
    if not ups and not news: return None
    return {"next": ups[0] if ups else None, "after": ups[1] if len(ups) > 1 else None, "news": news[:2]}

def _launch_when(x):
    N = _N(); t = _ts(x.get("net"))
    if not t: return ""
    et = t.astimezone(N.ET)
    if (x.get("precision") or "") in ("Month", "Quarter", "Half Year", "Year", "Fiscal Year"): return "No earlier than " + et.strftime("%B %Y")
    if (x.get("precision") or "") in ("Day", "Week"): return "No earlier than " + et.strftime("%a, %b %-d")
    s = et.strftime("%a, %b %-d · %-I:%M %p ET")
    we = _ts(x.get("win_end"))
    if we and we > t: s += " (window to " + we.astimezone(N.ET).strftime("%-I:%M %p ET") + ")"
    return s

def _launch_name(x):
    nm = str(x.get("name") or "")
    return (nm.split(" | ", 1)[1] if " | " in nm else (x.get("mission") or nm)).strip()

def _launch_site(x):
    return re.sub(r",\s*USA$", "", str(x.get("site") or "")).strip()

def _space_html(sx, c, refs):
    N = _N(); H = []
    nx = sx.get("next")
    if nx:
        refs.add("SpaceX launch schedule: The Space Devs, Launch Library 2 (times are no-earlier-than and often change).", "https://thespacedevs.com/llapi")
        meta = " · ".join(x for x in (_STATUS.get(nx.get("status") or "", ""), str(nx.get("rocket") or ""), _launch_site(nx)) if x)
        desc = summary({"title": "", "what": nx.get("desc") or ""}, 200) if nx.get("desc") else ""
        H += [f'<div class="bnm" style="font:700 {BODY_PX}px/22px {FACE};letter-spacing:1px;color:{MU};margin:0 0 4px 0">NEXT SPACEX LAUNCH</div>',
              _headline(_launch_name(nx)),
              _p(f'<b class="bnt" style="color:{TX}">{E(_launch_when(nx))}</b>', 8, TX, "bnt"), _p(E(meta), 2, MU, "bnm")]
        if desc: H.append(_p(E(desc), 8))
        af = sx.get("after")
        if af: H.append(_p(f"After that: {E(_launch_name(af))}, {E(_launch_when(af))}.", 8, MU, "bnm"))
    if sx.get("news"):
        H.append(f'<div class="bnm" style="font:700 {BODY_PX}px/22px {FACE};letter-spacing:1px;color:{MU};margin:{14 if nx else 0}px 0 0 0">SPACEX &amp; STARLINK IN THE NEWS</div>')
        for n_ in sx["news"]:
            i = refs.add(f"SpaceX news: {n_['source']}, \u201c{n_['title']}\u201d", n_["url"])
            H.append(_p(f'{E(n_["title"])} <span class="bnm" style="color:{MU}">({E(n_["source"])}, source {i})</span>', 6))
    H.append(_links(("SpaceX launch tracker", _base(c) + "/spacex")))
    return _card("".join(H), GROUPS["space"][1])

# ------------------------------------------------------------------ preparedness tip (existing /ready guides only)
_READY = {   # guide: (link label, checklist PDF on /static/ready, tips) -- tip copy is the site's own Prepare guidance
    "family": ("Family communication plan (PDF)", "/static/ready/04-family-communication-plan.pdf",
               ("Write one out-of-area contact and two meeting places, and save them in each phone.",
                "Agree on one out-of-area contact that everyone in the household can call or text.")),
    "aid": ("First aid and medication basics (PDF)", "/static/ready/05-first-aid-and-medication-basics.pdf",
            ("Keep a written list of each person's medicines, doses and allergies with your kit.",
             "Check the first-aid kit and the written list of medicines, doses and allergies.")),
    "water": ("Water at home (PDF)", "/static/ready/02-water-at-home.pdf",
              ("Store one gallon of drinking water per person per day.",)),
    "power": ("Power outage readiness (PDF)", "/static/ready/03-power-outage-readiness.pdf",
              ("Charge power banks and keep the fridge closed during an outage.",
               "Any generator stays outdoors, 20 feet from windows.")),
    "kit": ("72-hour home kit (PDF)", "/static/ready/01-72-hour-home-kit.pdf",
            ("Confirm the 72-hour bin: water, food the household already eats, a flashlight and a radio.",)),
}
_GROUP_READY = {"war": "family", "politics": "family", "health": "aid", "hazards": "water", "space": "power", "cyber": "kit", "money": "kit", "world": "kit"}

def tip_for(issue, groups):
    """(tip, label, path, group) tied to the issue's lead category; rotates daily within that guide."""
    g = groups[0][0] if groups else "world"
    lead = groups[0][1][0] if groups and groups[0][1] else {}
    t = (str(lead.get("title") or "") + " " + _N().card_headline(lead) if lead else "").lower()
    key = _GROUP_READY.get(g, "kit")
    if g == "hazards" and re.search(r"earthquake|quake", t): key = "aid"
    if g == "space" and not re.search(r"geomagnetic|solar|kp ", t): key = "power" if "space weather" in str(lead.get("category") or "") else "kit"
    lab, path, tips = _READY[key]
    day = issue["end"].astimezone(_N().ET).timetuple().tm_yday + (1 if issue.get("slot") == "evening" else 0)
    return tips[day % len(tips)], lab, path, g

def _tip_html(issue, groups, c):
    tip, lab, path, g = tip_for(issue, groups)
    return (f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:18px 16px 6px 16px;background:{BG}">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{SURF2}" style="background:{SURF2};border-radius:14px;border-collapse:separate">'
            f'<tr><td class="bns2" bgcolor="{SURF2}" style="padding:14px 16px 6px 16px;background:{SURF2};border-radius:14px;text-align:left">'
            f'<div class="bnr" style="font:700 {BODY_PX}px/22px {FACE};letter-spacing:1px;color:{AC}">PREPAREDNESS TIP</div>'
            + _p(E(tip), 4)
            + _links((E(lab), _base(c) + path), [("All guides", _base(c) + "/ready")])
            + '</td></tr></table></td></tr>')

def _video_card(s, c, camp, refs):
    N = _N(); base = _base(c); site = N.story_url(s["slug"], c, camp)
    yt = f'https://www.youtube.com/watch?v={s["youtube_id"]}' if s.get("youtube_id") else (s.get("youtube_url") or "https://www.youtube.com/@blkoutntw")
    pic = ""
    if s.get("thumb"):
        pic = _img_html({"src": f'{base}/social/thumb/{urllib.parse.quote(s["thumb"])}', "alt": s.get("thumb_alt") or f'Thumbnail: {s["title"]}'}, refs, s["title"])
    return _card(pic + _headline(s["title"]) + (_p(E(s.get("dek") or ""), 8) if s.get("dek") else "")
                 + _links(("Read &amp; watch", site), [("YouTube", yt)]))

def _head(title):
    N = _N()
    css = N._DARK_LOCK.replace(".bnh1{font-size:28px!important;line-height:32px!important}", ".bnh1{font-size:21px!important;line-height:27px!important}")
    return ('<!DOCTYPE html><html lang="en" xmlns="http://www.w3.org/1999/xhtml"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="x-apple-disable-message-reformatting"><meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark">'
            f'<title>{E(title)}</title><style>{css}</style></head>')

def _top_links(links):
    """Footer links without a #fragment, so every link opens at the top of its page (the shared v1 footer falls back to site/#wire)."""
    out = dict(links)
    for k in ("sources", "site", "categories", "manage"):
        if isinstance(out.get(k), str): out[k] = out[k].split("#", 1)[0]
    if not out.get("sources") and out.get("site"): out["sources"] = out["site"]
    return out

def _footer(links, c, why, refs, graphics):
    """Small (13px) footer: brand, disclaimer, the numbered credits/sources list, CAN-SPAM address, and every control as a
    right-aligned 44px text link (manage, sources, stop tracking, unsubscribe, breaking alerts)."""
    N = _N(); addr, addr_html = N._addr(c); L = _top_links(links)
    F = f"font:400 {FOOT_PX}px/19px {FACE};color:{MU}"
    lk = lambda lab, url: (f'<a href="{E(url)}" class="bnm" style="display:inline-block;padding:12px 0 12px 16px;font:600 {FOOT_PX + 1}px/20px {FACE};'
                           f'color:{TX};text-decoration:underline">{lab}</a>')
    ctl = [("YouTube @blkoutntw", "https://www.youtube.com/@blkoutntw"), ("X @BlkoutNtw", "https://x.com/BlkoutNtw"),
           ("How we score", L["scoring"]), ("Live dashboard", L["site"]), ("Forward to a friend", N.FORWARD_URL)]
    ctl2 = [("Manage my subscription categories", L.get("categories") or L.get("manage")), ("Find new sources", L.get("sources") or L.get("site"))]
    if L.get("stop_tracking"): ctl2.append(("Stop tracking my opens and clicks", L["stop_tracking"]))
    ctl2.append(("Unsubscribe (one click, no login)", L["unsubscribe"]))
    if L.get("breaking_off"): ctl2.append(("Stop breaking alerts (keep briefs)", L["breaking_off"]))
    rows = lambda items: ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td align="right" style="text-align:right">'
                          + "".join(lk(a, b) for a, b in items) + '</td></tr></table>')
    cred = ""
    if refs.items or graphics:
        li = "".join(f'<tr><td valign="middle" width="24" style="width:24px;{F}">{i}.</td><td valign="middle" style="{F};padding:2px 0;text-align:left">{E(t)}</td>'
                     f'<td valign="middle" align="right" width="64" style="width:64px;text-align:right">'
                     + (f'<a href="{E(u)}" class="bnm" style="display:inline-block;padding:12px 0 12px 10px;font:600 {FOOT_PX}px/20px {FACE};color:{MU};text-decoration:underline">Source</a>' if u else "")
                     + '</td></tr>' for i, (t, u) in enumerate(refs.items, 1))
        cred = (f'<div class="bnm" style="font:700 {FOOT_PX}px/19px {FACE};letter-spacing:1px;color:{MU};margin:14px 0 6px 0">IMAGE CREDITS &amp; SOURCES</div>'
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{li}</table>'
                + (f'<p style="margin:4px 0 0 0;{F}">Story graphics without a photo are made by {N.BRAND} from the story\'s own reports. '
                   f'Each story\'s sources are listed on its story page.</p>' if graphics else
                   f'<p style="margin:4px 0 0 0;{F}">Each story\'s sources are listed on its story page.</p>'))
    return ('<!--bn-footer-->' + f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:26px 16px 0 16px;background:{BG}">'
            f'<div style="height:1px;background:{LINE};font-size:0;line-height:1px">&nbsp;</div>{rows(ctl)}</td></tr>'
            f'<tr><td class="bnpad bnm" bgcolor="{BG}" style="padding:10px 16px 6px 16px;background:{BG};{F};text-align:left">'
            f'<div class="bnt" style="font:700 {FOOT_PX}px/18px {FACE};letter-spacing:1.4px;color:{TX}">BLACKOUT.NETWORK</div>'
            f'<div class="bnm" style="margin:2px 0 10px 0;color:{MU}">{E(N.TAGLINE)}</div>'
            f'<p style="margin:0 0 8px 0;{F}">{E(N.DISCLAIMER)} Every story links to its page on {N.BRAND}.</p>'
            f'<p style="margin:0 0 8px 0;{F}">{E(why)}</p>'
            f'<p style="margin:0;{F}">{N.BRAND} · {addr_html}</p>{cred}</td></tr>'
            f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:4px 16px 22px 16px;background:{BG}">{rows(ctl2)}</td></tr>')

# ------------------------------------------------------------------ render
_GROUP_SECS = ("main", "politics", "updates", "notable")

def _story_items(issue):
    dev_lead = [dict(it, section="developing") for it in issue.get("developing") or [] if it.get("lead")]
    seen, out = set(), []
    for it in [x for s in _GROUP_SECS for x in issue.get(s) or []] + dev_lead:
        cid = it.get("cluster_id")
        if cid in seen: continue
        seen.add(cid); out.append(it)
    return out

def render(issue, links, c):
    """-> (subject, html, text), same contract as newsletter.render."""
    N = _N(); subj = N.subject_for(issue); camp = f"{issue.get('slot') or 'brief'}-{issue['end'].astimezone(N.ET).strftime('%Y-%m-%d')}"
    N._number_map(issue)
    refs = Refs(); B = [_masthead(issue, c), _top3(issue, c)]
    feats = issue.get("featured") or []
    first = [True]
    def head(label, accent, sub=None):
        B.append(_group_head(label, accent, sub, first[0])); first[0] = False
    if feats:
        head("Featured", "#22C55E")
        B.extend(featured_card(f_, c, refs) for f_ in feats)
    if issue.get("near"):
        head(f"Near you · {issue.get('loc_label') or 'your area'}", AC, "Confirmed or official reports within about 300 km of your area.")
        B.extend(story_card(it, links, c, refs, AC) for it in issue["near"])
    if issue.get("crime"):
        cr = issue["crime"]
        head(f"Crime near you · {cr['label']}", AC, f"Official statistics and recent police reports. Source: {cr['source']}.")
        B.append(f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:4px 16px 6px 16px;background:{BG}">'
                 + "".join(_p(E(x), 4) for x in cr["lines"][:3]) + _links((f"Map and numbers for {E(cr['label'])}", cr["url"])) + '</td></tr>')
    if issue.get("follow"):
        head("Stories you follow", AC)
        B.extend(story_card(it, links, c, refs, AC) for it in issue["follow"])
    groups = grouped(issue, _story_items(issue))
    for g, items in groups:
        lab, acc = GROUPS[g]
        top = max(_rk(x) for x in items)
        sub = f'{len(items)} stor{"y" if len(items) == 1 else "ies"}' + (f" · highest rank {top}" if top >= 0 else "")
        head(lab, acc, sub)
        B.extend(story_card(it, links, c, refs, acc) for it in items)
    vids = issue.get("videos") or []
    if vids:
        head(f"Watch: new on {N.BRAND}", AC)
        B.extend(_video_card(s, c, issue["slot"], refs) for s in vids)
    sx = None
    try: sx = spacex_block(issue)
    except Exception: sx = None
    if sx:
        head(GROUPS["space"][0], GROUPS["space"][1])
        B.append(_space_html(sx, c, refs))
    rest = [it for it in issue.get("developing") or [] if not it.get("lead")]
    if rest or issue.get("watchlist"):
        head("Also on the wire", GROUPS["world"][1], "Short items. Watchlist items are single-source and not yet confirmed.")
        for it in rest:
            B.append(_line_item(N._cut(it["title"], 140), N.wire_url(it["cluster_id"], c=c), f'Rank {int(it.get("rank") or 0)} · first logged {E(N.fmt_et(it.get("first_seen")))}'))
        for it in issue.get("watchlist") or []:
            B.append(_line_item(N._cut(it["title"], 140), N.wire_url(it["cluster_id"], c=c),
                                f'<span class="ta" style="color:{AMBER}">Unconfirmed</span> · {E(N.fmt_et(it.get("first_seen")))}'))
    if groups or feats: B.append(_tip_html(issue, groups or [("world", [])], c))
    graphics = any('/newsletter/img/card/' in x for x in B if x)
    why = f"You get this because you confirmed a subscription to the {N.BRAND} newsletter. Change how often it arrives, or turn off breaking alerts, under Manage."
    pool = N._story_pool(issue)
    pre = (N.card_headline(pool[0]) + (f" + {len(pool) - 1} more, sorted by category and rank." if len(pool) > 1 else "")) if pool else N.MATTERS
    html_ = (_head(subj) + f'<body bgcolor="{BG}" class="bnb" style="margin:0;padding:0;background:{BG};color:{TX};-webkit-text-size-adjust:100%">'
             f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{BG}">{E(pre)}&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;</div>'
             f'<table role="presentation" class="bnb" bgcolor="{BG}" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG}"><tr><td bgcolor="{BG}" align="center" style="padding:0;background:{BG}">'
             '<!--[if mso]><table role="presentation" width="600" align="center" cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->'
             f'<table role="presentation" class="bnb" bgcolor="{BG}" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:{BG};font-family:{FACE};color:{TX};text-align:left">'
             + "".join(x for x in B if x) + _footer(links, c, why, refs, graphics) + '</table><!--[if mso]></td></tr></table><![endif]--></td></tr></table></body></html>')
    text = text_part(issue, links, c, subj, why, groups, sx, refs)
    return (subj,) + N.utm_tag(html_, text, camp)

def text_part(issue, links, c, subj, why, groups=None, sx=None, refs=None):
    N = _N(); addr, _ = N._addr(c); L = _top_links(links); refs = refs or Refs()
    groups = groups if groups is not None else grouped(issue, _story_items(issue))
    day = issue.get("label") or issue["end"].astimezone(N.ET).strftime("%A, %B %-d, %Y")
    T = [subj, "", f"{N.BRAND} · {N.TAGLINE}", f"{N.slot_label(issue['slot'])} brief · {day}", "", N.MATTERS + "."]
    pool = top_stories(issue, 3)
    if pool:
        T.append("TOP 3 RIGHT NOW")
        T += [f"{i}. {N.card_headline(it)}" for i, it in enumerate(pool, 1)] + [""]
    elif not issue.get("featured"):
        T += [f"Open the live dashboard: {_base(c)}/", ""]
    for f_ in issue.get("featured") or []:
        T += [f_["kicker"].upper() + (f" · {f_['tag'].upper()}" if f_.get("tag") else ""), f_["title"]] + ([f_["text"]] if f_.get("text") else []) + [f"Read the full brief: {f_['url']}", ""]
    def one(it, i):
        rk = "" if it.get("rank") is None else f"[Rank {int(it.get('rank') or 0)}/10] "
        T.append(f"{i}. {rk}{N.card_headline(it)}")
        s = summary(it)
        if s: T.append(f"   {s}")
        for p in people_of(it, c): T.append(f"   Profile, {p['name']}: {p['url']}")   # one per line: a trailing ";" would end up inside the tagged URL
        T.append(f"   Read the full brief: {N.wire_url(it['cluster_id'], c=c)}")
        yt = youtube_for(it); xu = x_for(it)
        if yt: T.append(f"   YouTube: {yt}")
        if xu: T.append(f"   X: {xu}")
        T.append("")
    def tsec(title, items):
        if not items: return
        T.extend([title.upper(), "=" * len(title)])
        for i, it in enumerate(items, 1): one(it, i)
    if issue.get("near"): tsec(f"Near you · {issue.get('loc_label') or 'your area'}", issue["near"])
    if issue.get("crime"):
        cr = issue["crime"]; T += [f"CRIME NEAR YOU · {cr['label'].upper()}"] + cr["lines"][:3] + [f"Map and full numbers: {cr['url']}", ""]
    tsec("Stories you follow", issue.get("follow"))
    for g, items in groups: tsec(GROUPS[g][0], items)
    for s_ in issue.get("videos") or []: T.extend(N._video_text(s_, c, issue["slot"]))
    if sx:
        T += [GROUPS["space"][0].upper(), "=" * len(GROUPS["space"][0])]
        nx = sx.get("next")
        if nx:
            T += [f"Next SpaceX launch: {_launch_name(nx)}", f"   {_launch_when(nx)}",
                  "   " + " · ".join(x for x in (_STATUS.get(nx.get('status') or '', ''), str(nx.get('rocket') or ''), _launch_site(nx)) if x)]
            if sx.get("after"): T.append(f"   After that: {_launch_name(sx['after'])}, {_launch_when(sx['after'])}.")
        for n_ in sx.get("news") or []: T.append(f"- {n_['title']} ({n_['source']})")
        T += [f"SpaceX launch tracker: {_base(c)}/spacex", ""]
    rest = [it for it in issue.get("developing") or [] if not it.get("lead")]
    if rest or issue.get("watchlist"):
        T += ["ALSO ON THE WIRE", "=" * 16]
        T += [f"- Rank {int(it.get('rank') or 0)} {it['title']} (first logged {N.fmt_et(it.get('first_seen'))}) {N.wire_url(it['cluster_id'], c=c)}" for it in rest]
        T += [f"- UNCONFIRMED · {N._cut(it['title'], 180)} ({N.fmt_et(it['first_seen'])}) {N.wire_url(it['cluster_id'], c=c)}" for it in issue.get("watchlist") or []]
        T.append("")
    if groups or issue.get("featured"):
        tip, lab, path, _g = tip_for(issue, groups or [("world", [])])
        T += ["PREPAREDNESS TIP", tip, f"{lab}: {_base(c)}{path}", f"All guides: {_base(c)}/ready", ""]
    T += [f"Forward to a friend: {N.FORWARD_URL}", N.END_LINE, "https://blackout.network · YouTube: https://www.youtube.com/@blkoutntw · X: https://x.com/BlkoutNtw", ""]
    T += ["--", N.DISCLAIMER, f"How we score: {L['scoring']}", f"Dashboard: {L['site']}", why,
          f"{N.BRAND} · {N.TAGLINE}", f"{addr or 'Postal address: [PENDING] (required by CAN-SPAM before live sending)'}", ""]
    if refs.items:
        T.append("IMAGE CREDITS & SOURCES")
        T += [f"{i}. {t}" + (f" {u}" if u else "") for i, (t, u) in enumerate(refs.items, 1)] + ["Each story's sources are listed on its story page.", ""]
    T += N.footer_buttons_text(L)
    return "\n".join(T)
