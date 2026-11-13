"""BLACKOUT.NETWORK brief, layout v2 (Matt, Nov 13 2026, t1365u): shorter, scannable, one credited picture per story.

Off by default. On with the Render env BN_NL_V2=1 (or "template": "v2" in newsletter_config.json); newsletter.render() calls
render() here and falls back to the v1 layout if anything in this module raises. Issue selection, the brief gate, the
Hamas pin / featured desk stories, the QA gate, tracking and every footer link are unchanged: this module only draws.

Per story card
  * picture: a rights-cleared image from the signed story_reports.json, else the story page's own file-photo pick
    (people.lead_for: the person named in the headline, else the country or place), else a "story at a glance" graphic drawn
    from the story's own data. Every picture is served from blackout.network (newsletter_img.py) and carries a credit line.
  * kicker (rank in its band colour, category, place), the headline, a one-sentence summary, the people named in the story
    (small headshot + "Profile" link to /people/<slug>), and the buttons: "Read the full brief" (the /wire page), plus
    "Watch on YouTube" when our video of the story is live (social_links.json, or a social_stories.json video).
Email-safe: one 600px table column, inline styles, hosted JPEG/PNG only (no data: URIs, no WebP, no SVG), dark plates kept in
light-mode clients (same lock as v1), all text left-aligned, 44px tap targets.
"""
import html, os, re, urllib.parse

E = lambda s: html.escape("" if s is None else str(s), quote=True)
FACE = "Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
BG, SURF, SURF2, LINE = "#0B0C0F", "#16181C", "#1C1F24", "#2A2D33"
TX, BODY, MU, AC, INK = "#F5F5F7", "#D2D2D7", "#A1A1A6", "#FFC21A", "#0B0C0F"
RED, AMBER, GREEN = "#C8102E", "#FFC21A", "#3FA66A"
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
                    "credit_html": _credit_html(im)}
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
                    "credit_html": _credit_html(fb)}
    n = int(it.get("n_items") or 0)
    built = f"built from the {n} reports on this story" if n > 1 else "built from this story's own reports"
    return {"src": f"{base}/newsletter/img/card/{cid}.png", "kind": "graphic",
            "alt": f"Story at a glance: rank {int(it.get('rank') or 0)} of 10" + (f", {it['where']}" if it.get("where") else ""),
            "credit_html": f"Graphic: {N.BRAND}, {built}. No rights-cleared photo of this event was available."}

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
        out.append({"slug": slug, "name": p.get("name") or slug, "role": p.get("role") or "",
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
    if rk >= 7:
        return (f'<span style="display:inline-block;background:{RED};color:#FFFFFF;border-radius:999px;padding:3px 10px;'
                f'font:700 12px/16px {FACE};letter-spacing:.4px">Rank {rk} · {E(name)}</span>')
    col = AMBER if rk >= 4 else GREEN
    return f'<span class="{"ta" if rk >= 4 else ""}" style="font:700 12px/16px {FACE};color:{col};letter-spacing:.4px">Rank {rk} · {E(name)}</span>'

def _place_named(place, it):
    text = " ".join(str(x or "") for x in (it.get("display_title"), it.get("title")))   # the headline must name it
    words = [w for w in re.findall(r"[A-Za-z\u00C0-\u024F'-]{4,}", place) if w.lower() not in ("approx", "near", "city", "region", "province", "county", "state")]
    return any(re.search(r"\b" + re.escape(w[:-1] if w.endswith("e") else w), text, re.I) for w in words) if words else False

def _kicker(it, extra=None):
    N = _N(); sep = f'<span style="color:{MU}"> · </span>'
    parts = [x for x in (_rank_chip(it),) if x]
    cat = (it.get("category") or "").strip()
    if cat and cat.lower() != "other": parts.append(f'<span class="bnm" style="color:{MU}">{E(cat.upper())}</span>')
    place = (it.get("where") or "").strip()
    if place and not _place_named(place, it): place = ""   # a scanner place the story text never names is left off (pre-publish A2)
    if place: parts.append(f'<span class="bnm" style="color:{MU}">{E(N._one_line(place, 34))}</span>')
    if it.get("breaking"): parts.append(f'<span style="color:{RED};font-weight:700">BREAKING</span>')
    if it.get("update"): parts.append(f'<span class="ta" style="color:{AMBER}">UPDATE</span>')
    if it.get("editorial") or it.get("section") == "watchlist": parts.append(f'<span class="ta" style="color:{AMBER}">UNCONFIRMED</span>')
    for x in extra or (): parts.append(x)
    return f'<div style="font:600 12px/18px {FACE};letter-spacing:.6px;margin:0 0 8px 0">{sep.join(parts)}</div>'

def _img_html(im, url):
    return (f'<a href="{E(url)}" style="text-decoration:none"><img src="{E(im["src"])}" width="{IMG_W}" alt="{E(im["alt"])}" '
            f'style="display:block;width:100%;max-width:{IMG_W}px;height:auto;border:0;border-radius:12px;background:{SURF2};'
            f'color:{MU};font:400 13px/18px {FACE}"></a>'
            f'<div class="bnm" style="margin:6px 0 12px 0;font:400 11px/16px {FACE};color:{MU}">{im["credit_html"]}</div>')

def _btn(label, url, primary=True):
    st = (f"background:{AC};color:{INK};border:1px solid {AC}" if primary else f"background:{SURF};color:{TX};border:1px solid #3A3E46")
    return (f'<a href="{E(url)}" class="{"bnp" if primary else "bng"}" style="display:inline-block;{st};font:700 15px/20px {FACE};'
            f'text-decoration:none;border-radius:999px;padding:12px 18px;margin:12px 8px 0 0;mso-padding-alt:0">{label}</a>')

def _people_html(ps):
    if not ps: return ""
    cells = []
    for p in ps:
        pic = (f'<img src="{E(p["img"])}" width="36" height="36" alt="{E(p["name"])}" style="display:block;width:36px;height:36px;'
               f'border:0;border-radius:18px;background:{SURF2}">' if p["img"] else
               f'<div style="width:36px;height:36px;border-radius:18px;background:{SURF2};color:{TX};font:700 13px/36px {FACE};text-align:center">'
               f'{E("".join(w[0] for w in p["name"].split()[:2]))}</div>')
        cells.append(f'<div style="display:inline-block;vertical-align:top;margin:8px 16px 0 0">'
                     f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
                     f'<td valign="middle" style="padding:0 8px 0 0"><a href="{E(p["url"])}" style="text-decoration:none">{pic}</a></td>'
                     f'<td valign="middle" style="font:600 13px/17px {FACE};color:{TX}"><span class="bnt" style="color:{TX}">{E(p["name"])}</span><br>'
                     f'<a href="{E(p["url"])}" class="bnr" style="font:600 12px/17px {FACE};color:{AC};text-decoration:underline">Profile</a></td>'
                     f'</tr></table></div>')
    cr = [f'{p["name"]}: {p["credit"]}' for p in ps if p.get("credit")]
    crh = (f'<div class="bnm" style="margin:6px 0 0 0;font:400 11px/16px {FACE};color:{MU}">Headshots: {E("; ".join(cr))}.</div>' if cr else "")
    return (f'<div style="margin:12px 0 0 0;padding:10px 0 0 0;border-top:1px solid {LINE}">'
            f'<div class="bnm" style="font:600 11px/14px {FACE};letter-spacing:1px;color:{MU}">PEOPLE IN THIS STORY</div>'
            + "".join(cells) + crh + '</div>')

def _card(inner, accent=None):
    top = (f'<tr><td height="4" bgcolor="{accent}" style="height:4px;background:{accent};font-size:0;line-height:0;border-radius:16px 16px 0 0">&nbsp;</td></tr>'
           if accent else "")
    return (f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:8px 16px;background:{BG}">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{SURF}" class="bncard" '
            f'style="background:{SURF};border-radius:16px;border-collapse:separate">{top}'
            f'<tr><td class="bncard" bgcolor="{SURF}" style="padding:16px;background:{SURF};border-radius:16px;color:{TX};word-break:break-word;overflow-wrap:anywhere">'
            f'{inner}</td></tr></table></td></tr>')

def story_card(it, links, c, num=None):
    N = _N(); url = N.wire_url(it["cluster_id"], c=c); head = N.card_headline(it)
    im = lead_image(it, c); ps = people_of(it, c); yt = youtube_for(it); u = it.get("update")
    H = [_img_html(im, url), _kicker(it),
         f'<a href="{E(url)}" class="bnt bnh1" style="font:700 21px/27px {FACE};color:{TX};text-decoration:none">{E(head)}</a>']
    if u:
        bits = []
        if u.get("rank_from") is not None and u["rank_from"] != u.get("rank_to"):
            bits.append(f"Rank {'raised' if u.get('up') else 'lowered'} {u['rank_from']} to {u['rank_to']}.")
        if u.get("n_new"): bits.append(f"{u['n_new']} new report{'s' if u['n_new'] != 1 else ''}.")
        H.append(f'<p class="bnx" style="margin:8px 0 0 0;font:400 15px/22px {FACE};color:{BODY}"><b class="ta" style="color:{AMBER}">What\'s new:</b> {E(" ".join(bits) or "Updated.")}</p>')
    s = summary(it)
    if s: H.append(f'<p class="bnx" style="margin:8px 0 0 0;font:400 15px/22px {FACE};color:{BODY}">{E(s)}</p>')
    H.append(_people_html(ps))
    btns = _btn("Read the full brief", url) + (_btn("Watch on YouTube", yt, primary=False) if yt else "")
    fl = N.follow_links(links.get("_row"), it["cluster_id"], c)
    fol = ""
    if links.get("_row") and fl.get("follow"):   # subscriber token links only; previews skip the #follow anchor
        fol = (f'<a href="{E(fl["unfollow"])}" class="bnm" style="font:400 13px/20px {FACE};color:{MU}">Unfollow</a>' if it.get("followed") and fl.get("unfollow")
               else f'<a href="{E(fl["follow"])}" class="bnm" style="font:400 13px/20px {FACE};color:{MU};text-decoration:underline">Follow this story</a>')
        fol = f'<div style="margin:10px 0 0 0">{fol}</div>'
    H.append(f'<div>{btns}</div>{fol}')
    return _card("".join(H))

def featured_card(f_, c):
    N = _N(); it = {"cluster_id": f_["cluster_id"], "title": f_["title"], "display_title": f_["title"], "rank": None, "where": ""}
    try:
        import desk_stories as DS
        s = DS.get(f_["cluster_id"]) or {}
        it.update(rank=s.get("rank"), where=s.get("location") or "", n_items=len(s.get("reports") or []))
    except Exception:
        pass
    im = lead_image(it, c, title=f_["title"]); ps = people_of(dict(it, what=f_.get("text")), c, title=f_["title"])
    kick = E(f_["kicker"].upper()) + ((" · " + E(f_["tag"].upper())) if f_.get("tag") else "")
    H = [_img_html(im, f_["url"]),
         f'<div style="font:700 12px/18px {FACE};letter-spacing:.8px;color:#22C55E;margin:0 0 8px 0">{kick}</div>',
         f'<a href="{E(f_["url"])}" class="bnt bnh1" style="font:700 21px/27px {FACE};color:{TX};text-decoration:none">{E(f_["title"])}</a>']
    if f_.get("text"):
        H.append(f'<p class="bnx" style="margin:8px 0 0 0;font:400 15px/22px {FACE};color:{BODY}">{E(f_["text"])}</p>')
    H.append(_people_html(ps))
    yt = youtube_for(it)
    H.append("<div>" + _btn("Read the full brief", f_["url"]) + (_btn("Watch on YouTube", yt, primary=False) if yt else "") + "</div>")
    return _card("".join(H), accent="#22C55E")

def _sec(title, sub=None):
    return (f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:22px 16px 4px 16px;background:{BG}">'
            f'<div class="bnt" style="font:700 13px/18px {FACE};letter-spacing:1.4px;color:{TX}">{E(title.upper())}</div>'
            + (f'<div class="bnm" style="font:400 13px/18px {FACE};color:{MU};margin-top:2px">{E(sub)}</div>' if sub else "")
            + f'<div style="height:2px;width:32px;background:{AC};margin-top:8px;font-size:0;line-height:2px">&nbsp;</div></td></tr>')

def _line_item(title, url, meta):
    return (f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:6px 16px;background:{BG}">'
            f'<a href="{E(url)}" class="bnt" style="font:600 15px/21px {FACE};color:{TX};text-decoration:underline">{E(title)}</a>'
            f'<div class="bnm" style="font:400 12px/17px {FACE};color:{MU};margin-top:2px">{meta}</div></td></tr>')

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
    head = (f'<div class="bnt" style="font:700 20px/26px {FACE};color:{TX};margin:0 0 2px 0">{N.MATTERS}</div>')
    if not pool:   # quiet issue: the heading and a dashboard link only, nothing invented
        if issue.get("featured"): return ""
        return (f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:4px 16px 8px 16px;background:{BG}">'
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{SURF}" style="background:{SURF};border-radius:16px;border-collapse:separate">'
                f'<tr><td class="bns" bgcolor="{SURF}" style="padding:16px 18px;background:{SURF};border-radius:16px">{head}'
                f'<div style="margin-top:4px">{_btn("Open the live dashboard", _base(c) + "/")}</div>'   # no empty-state sentence (test _EMPTY rule)
                '</td></tr></table></td></tr>')
    li = "".join(f'<tr><td valign="top" style="padding:10px 0 0 0;font:400 15px/21px {FACE}">'
                 f'<a href="{E(N.wire_url(it["cluster_id"], c=c))}" class="bnt" style="color:{TX};text-decoration:none">'
                 f'<b style="font-weight:700">{i}. {E(N.card_headline(it))}</b></a></td></tr>' for i, it in enumerate(pool, 1))
    n = len(N._story_pool(issue)) + len(issue.get("featured") or [])
    mins = max(1, round(n * 0.5))
    return (f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:4px 16px 8px 16px;background:{BG}">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{SURF}" style="background:{SURF};border-radius:16px;border-collapse:separate">'
            f'<tr><td class="bns" bgcolor="{SURF}" style="padding:16px 18px;background:{SURF};border-radius:16px">'
            f'<div class="bnr" style="font:700 12px/16px {FACE};letter-spacing:1.2px;color:{AC};margin:0 0 4px 0">TOP 3 RIGHT NOW</div>{head}'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{li}</table>'
            f'<div class="bnm" style="font:400 12px/17px {FACE};color:{MU};margin-top:10px">{n} stor{"y" if n == 1 else "ies"} in this brief · about {mins} min to read</div>'
            '</td></tr></table></td></tr>')

def _masthead(issue, c):
    N = _N(); lab = N.slot_label(issue["slot"]); day = issue.get("label") or issue["end"].astimezone(N.ET).strftime("%A, %B %-d, %Y")
    logo = N.logo_url("dark", c)
    return (f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:20px 16px 14px 16px;background:{BG}">'
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td valign="middle" style="padding:0 12px 0 0"><a href="{_base(c)}"><img src="{E(logo)}" width="44" height="44" alt="BLACKOUT.NETWORK" '
            f'style="display:block;width:44px;height:44px;border:0;border-radius:10px"></a></td>'
            f'<td valign="middle"><div class="bnt" style="font:800 19px/23px {FACE};letter-spacing:1.2px;color:{TX}">BLACKOUT.NETWORK</div>'
            f'<div class="bnm" style="font:400 13px/18px {FACE};color:{MU}">{E(N.TAGLINE)}</div></td></tr></table>'
            f'<div class="bnr" style="font:700 13px/18px {FACE};letter-spacing:1px;color:{AC};margin-top:14px">{E(lab.upper())} BRIEF · {E(day.upper())}</div>'
            '</td></tr>')

def _video_card(s, c, camp):
    N = _N(); base = _base(c); site = N.story_url(s["slug"], c, camp)
    yt = f'https://www.youtube.com/watch?v={s["youtube_id"]}' if s.get("youtube_id") else (s.get("youtube_url") or "https://www.youtube.com/@blkoutntw")
    pic = ""
    if s.get("thumb"):
        pic = _img_html({"src": f'{base}/social/thumb/{urllib.parse.quote(s["thumb"])}', "alt": s.get("thumb_alt") or f'Thumbnail: {s["title"]}',
                         "credit_html": f"Image: {N.BRAND} video thumbnail."}, site)
    return _card(pic + f'<a href="{E(site)}" class="bnt" style="font:700 19px/25px {FACE};color:{TX};text-decoration:none">{E(s["title"])}</a>'
                 + (f'<p class="bnx" style="margin:8px 0 0 0;font:400 15px/22px {FACE};color:{BODY}">{E(s.get("dek") or "")}</p>' if s.get("dek") else "")
                 + "<div>" + _btn(f"Read &amp; watch on {N.BRAND}", site) + _btn("Watch on YouTube", yt, primary=False) + "</div>")

def _head(title):
    N = _N()
    css = N._DARK_LOCK.replace(".bnh1{font-size:28px!important;line-height:32px!important}", ".bnh1{font-size:20px!important;line-height:26px!important}")
    css += "@media only screen and (max-width:480px){.bnp,.bng{display:block!important;text-align:center!important;margin-right:0!important}}"
    return ('<!DOCTYPE html><html lang="en" xmlns="http://www.w3.org/1999/xhtml"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="x-apple-disable-message-reformatting"><meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark">'
            f'<title>{E(title)}</title><style>{css}</style></head>')

def _footer(links, c, why):
    N = _N(); addr, addr_html = N._addr(c)
    L = f"color:{TX};text-decoration:underline"
    soc = (f'<tr><td class="bnpad" bgcolor="{BG}" style="padding:20px 16px 4px 16px;background:{BG}">'
           + _btn("YouTube @blkoutntw", "https://www.youtube.com/@blkoutntw", primary=False) + _btn("X @BlkoutNtw", "https://x.com/BlkoutNtw", primary=False)
           + '</td></tr>')
    return (soc + f'<tr><td class="bnpad bnm" bgcolor="{BG}" style="padding:20px 16px 6px 16px;background:{BG};border-top:1px solid {LINE};font:400 12px/18px {FACE};color:{MU}">'
            f'<div class="bnt" style="font:700 12px/16px {FACE};letter-spacing:1.4px;color:{TX}">BLACKOUT.NETWORK</div>'
            f'<div class="bnm" style="margin:2px 0 10px 0;color:{MU}">{E(N.TAGLINE)}</div>'
            f'<p style="margin:0 0 8px 0">{E(N.DISCLAIMER)} Every story links to its page on {N.BRAND}, where you can open each original source. '
            f'<a href="{E(links["scoring"])}" class="bnt" style="{L}">How we score</a> · <a href="{E(links["site"].split("#", 1)[0])}" class="bnt" style="{L}">Open the live dashboard</a></p>'
            f'<p style="margin:0 0 8px 0">{E(why)}</p>'
            f'<p style="margin:0 0 8px 0">Know someone who should get this? <a href="{N.FORWARD_URL}" class="bnt" style="{L}">Forward to a friend: blackout.network/newsletter</a></p>'
            f'<p style="margin:0">{N.BRAND} · {addr_html}</p></td></tr>' + N.footer_buttons_html(_top_links(links)))

def _top_links(links):
    """Footer button links without a #fragment, so every link opens at the top of its page (the shared v1 footer falls back to site/#wire)."""
    out = dict(links)
    for k in ("sources", "site", "categories", "manage"):
        if isinstance(out.get(k), str): out[k] = out[k].split("#", 1)[0]
    if not out.get("sources") and out.get("site"): out["sources"] = out["site"]
    return out

# ------------------------------------------------------------------ render
def render(issue, links, c):
    """-> (subject, html, text), same contract as newsletter.render."""
    N = _N(); subj = N.subject_for(issue); camp = f"{issue.get('slot') or 'brief'}-{issue['end'].astimezone(N.ET).strftime('%Y-%m-%d')}"
    N._number_map(issue)
    B = [_masthead(issue, c), _top3(issue, c)]
    feats = issue.get("featured") or []
    if feats:
        B.append(_sec("Featured"))
        B.extend(featured_card(f_, c) for f_ in feats)
    def sec(title, items, sub=None):
        if not items: return
        B.append(_sec(title, sub))
        for it in items: B.append(story_card(it, links, c))
    if issue.get("near"): sec(f"Near you · {issue.get('loc_label') or 'your area'}", issue["near"], "Confirmed or official reports within about 300 km of your area.")
    if issue.get("crime"):
        cr = issue["crime"]
        B.append(_sec(f"Crime near you · {cr['label']}", f"Official statistics and recent police reports. Source: {cr['source']}."))
        B.append(f'<tr><td class="bnpad bnx" bgcolor="{BG}" style="padding:4px 16px 6px 16px;background:{BG};font:400 15px/22px {FACE};color:{BODY}">'
                 + "".join(f'<p style="margin:0 0 6px 0">{E(x)}</p>' for x in cr["lines"][:3])
                 + f'<p style="margin:4px 0 8px 0"><a href="{E(cr["url"])}" class="bnt" style="color:{TX};text-decoration:underline">Map and full numbers for {E(cr["label"])}</a></p></td></tr>')
    sec("Stories you follow", issue.get("follow"))
    sec("Top threats", _notes_order(issue, issue.get("main")), "New since your last brief, in the order of the Top 3.")
    sec("Politics & government", issue.get("politics"))
    vids = issue.get("videos") or []
    if vids:
        B.append(_sec(f"Watch: new on {N.BRAND}"))
        B.extend(_video_card(s, c, issue["slot"]) for s in vids)
    sec("Developing stories", issue.get("updates"), "Only what changed since your last brief.")
    dev = issue.get("developing") or []
    sec("Still developing", [it for it in dev if it.get("lead")])
    rest = [it for it in dev if not it.get("lead")]
    if rest:
        if not any(it.get("lead") for it in dev): B.append(_sec("Still developing", "Logged before this brief's window."))
        for it in rest:
            B.append(_line_item(N._cut(it["title"], 140), N.wire_url(it["cluster_id"], c=c), f'Rank {int(it.get("rank") or 0)} · first logged {E(N.fmt_et(it.get("first_seen")))}'))
    sec("Also notable", issue.get("notable"))
    if issue.get("watchlist"):
        B.append(_sec("Watchlist: unconfirmed", "Single-source reports. Not yet confirmed."))
        for it in issue["watchlist"]:
            B.append(_line_item(N._cut(it["title"], 140), N.wire_url(it["cluster_id"], c=c),
                                f'<span class="ta" style="color:{AMBER}">UNCONFIRMED</span> · {E((it.get("category") or "").upper())} · {E(N.fmt_et(it.get("first_seen")))}'))
    why = f"You get this because you confirmed a subscription to the {N.BRAND} newsletter. Change how often it arrives, or turn off breaking alerts, under Manage."
    pool = N._story_pool(issue)
    pre = (N.card_headline(pool[0]) + (f" + {len(pool) - 1} more stories with photos, sources and full briefs." if len(pool) > 1 else "")) if pool else N.MATTERS
    html_ = (_head(subj) + f'<body bgcolor="{BG}" class="bnb" style="margin:0;padding:0;background:{BG};color:{TX};-webkit-text-size-adjust:100%">'
             f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{BG}">{E(pre)}&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;</div>'
             f'<table role="presentation" class="bnb" bgcolor="{BG}" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG}"><tr><td bgcolor="{BG}" align="center" style="padding:0;background:{BG}">'
             '<!--[if mso]><table role="presentation" width="600" align="center" cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->'
             f'<table role="presentation" class="bnb" bgcolor="{BG}" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:{BG};font-family:{FACE};color:{TX};text-align:left">'
             + "".join(x for x in B if x) + _footer(links, c, why) + '</table><!--[if mso]></td></tr></table><![endif]--></td></tr></table></body></html>')
    text = text_part(issue, links, c, subj, why)
    return (subj,) + N.utm_tag(html_, text, camp)

def text_part(issue, links, c, subj, why):
    N = _N(); addr, _ = N._addr(c)
    day = issue.get("label") or issue["end"].astimezone(N.ET).strftime("%A, %B %-d, %Y")
    T = [subj, "", f"{N.BRAND} · {N.TAGLINE}", f"{N.slot_label(issue['slot'])} brief · {day}", ""]
    pool = top_stories(issue, 3)
    T.append(N.MATTERS + ".")
    if pool:
        T.append("TOP 3 RIGHT NOW")
        T += [f"{i}. {N.card_headline(it)}" for i, it in enumerate(pool, 1)] + [""]
    elif not issue.get("featured"):
        T += [f"Open the live dashboard: {_base(c)}/", ""]
    for f_ in issue.get("featured") or []:
        T += [f_["kicker"].upper() + (f" · {f_['tag'].upper()}" if f_.get("tag") else ""), f_["title"]] + ([f_["text"]] if f_.get("text") else []) + [f"Read the full brief: {f_['url']}", ""]
    def tsec(title, items):
        if not items: return
        T.extend([title.upper(), "=" * len(title)])
        for i, it in enumerate(items, 1):
            rk = "" if it.get("rank") is None else f"[Rank {int(it.get('rank') or 0)}/10 · {it.get('category') or ''}] "
            T.append(f"{i}. {rk}{N.card_headline(it)}")
            s = summary(it)
            if s: T.append(f"   {s}")
            ps = people_of(it, c)
            for p in ps: T.append(f"   Profile, {p['name']}: {p['url']}")   # one per line: a trailing ";" would end up inside the tagged URL
            T.append(f"   Read the full brief: {N.wire_url(it['cluster_id'], c=c)}")
            yt = youtube_for(it)
            if yt: T.append(f"   Watch on YouTube: {yt}")
            T.append("")
    if issue.get("near"): tsec(f"Near you · {issue.get('loc_label') or 'your area'}", issue["near"])
    if issue.get("crime"):
        cr = issue["crime"]; T += [f"CRIME NEAR YOU · {cr['label'].upper()}"] + cr["lines"][:3] + [f"Map and full numbers: {cr['url']}", ""]
    tsec("Stories you follow", issue.get("follow")); tsec("Top threats", _notes_order(issue, issue.get("main"))); tsec("Politics & government", issue.get("politics"))
    for s_ in issue.get("videos") or []: T.extend(N._video_text(s_, c, issue["slot"]))
    tsec("Developing stories", issue.get("updates"))
    tsec("Still developing", [it for it in issue.get("developing") or [] if it.get("lead")])
    for it in [it for it in issue.get("developing") or [] if not it.get("lead")]:
        T.append(f"- Rank {int(it.get('rank') or 0)} {it['title']} (first logged {N.fmt_et(it.get('first_seen'))}) {N.wire_url(it['cluster_id'], c=c)}")
    tsec("Also notable", issue.get("notable"))
    if issue.get("watchlist"):
        T += ["WATCHLIST: UNCONFIRMED (single-source, not yet confirmed)", "=" * 30]
        T += [f"- UNCONFIRMED · {N._cut(it['title'], 180)} ({it['category']}, {N.fmt_et(it['first_seen'])}) {N.wire_url(it['cluster_id'], c=c)}" for it in issue["watchlist"]] + [""]
    T += [f"Forward to a friend: {N.FORWARD_URL}", N.END_LINE, "https://blackout.network · YouTube: https://www.youtube.com/@blkoutntw · X: https://x.com/BlkoutNtw", ""]
    T += ["--", N.DISCLAIMER, f"How we score: {links['scoring']}", f"Dashboard: {links['site'].split('#', 1)[0]}", why,
          f"{N.BRAND} · {N.TAGLINE}", f"{addr or 'Postal address: [PENDING] (required by CAN-SPAM before live sending)'}", ""]
    T += N.footer_buttons_text(_top_links(links))
    return "\n".join(T)
