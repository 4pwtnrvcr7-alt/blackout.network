"""BLACKOUT.NETWORK brief, layout v4 (Matt, Nov 17 2026 4:11 PM ET): the site's SpaceX-style design in email.

On by default. Kill switch: Render env BN_NL_V4=0 (or "template": "v2"/"v1" in newsletter_config.json) -> layout v2.
newsletter.render() calls render() here first and falls back to v2 (then v1) if anything in this module raises.
Issue selection, the brief gate, the QA gate (same data-bn-h headline markers), tracking and every footer control are unchanged.

Design: near-black, white/grey type, generous spacing, minimal text. Plain-text "blackout.network" wordmark,
"Global threat monitoring" tagline. One large full-width lead image, then each story: picture, rank line (option A: greys
brightening to white, red only for 7+), short headline, one-sentence summary, outlined white "Read the full story" button.
No credits under images (footer "Image credits" link to /credits), no yellow/green/amber, no PayPal/donate.
Email-safe: one 600px table column, inline styles, hosted JPEG/PNG only, dark locked for iOS Mail / Apple Mail.
"""
import html, os
import newsletter_v2 as V2

E = lambda s: html.escape("" if s is None else str(s), quote=True)
FACE = V2.FACE
BG, SURF, LINE = "#000000", "#0E0F11", "#26282C"
TX, BODY, MU, DIM = "#FFFFFF", "#C7C7CC", "#8E8E93", "#6E6E73"
RED = "#FF4D4F"
WORDMARK, TAGLINE = "blackout.network", "Global threat monitoring"
RANK_GREY = {0: "#636366", 1: "#636366", 2: "#6E6E73", 3: "#7C7C80", 4: "#8E8E93", 5: "#AEAEB2", 6: "#E5E5EA"}
W = 600

def on(c=None):
    if os.environ.get("BN_NL_V4", "").strip() == "0": return False
    return str((c or {}).get("template") or "").lower() not in ("v1", "v2")

def _N(): return V2._N()

def HERO_STILL(c):
    """The site's own full-screen hero still (Earth from orbit, listed on /credits). Used when the lead story has no real photo."""
    return {"src": f"{V2._base(c)}/bnt/media/planet-d.jpg", "alt": "Earth from orbit", "kind": "hero", "credit": None}

# ------------------------------------------------------------------ topic divider images (Matt 4:21 PM: fresh every issue)
TOPIC_LABEL = {"war": "War & Conflict", "health": "Outbreaks & Health", "hazards": "Weather & Disasters", "cyber": "Cyber & Infrastructure",
               "politics": "Politics", "space": "Space", "money": "Money & Markets", "world": "World"}
_POOL = None
def pool():
    global _POOL
    if _POOL is None:
        try:
            import json
            d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "newsletter_pool.json")))
            _POOL = {}
            for im in d.get("images") or []: _POOL.setdefault(im["topic"], []).append(im)
        except Exception:
            _POOL = {}
    return _POOL

def issue_no(issue):
    """Monotonic issue number: two per day (morning/evening; breaking/special share the evening slot's neighbour)."""
    N = _N(); d = issue["end"].astimezone(N.ET).date()
    return d.toordinal() * 2 + (0 if issue.get("slot") == "morning" else 1)

LOG = "/workspace/launch/newsletter/nl_image_log.json"   # box-only used-image log (absent on Render: skipped)
def pick(topic, issue, c):
    """Divider image for one topic in this issue: rotates through the topic's pool one step per issue, so an image never comes
    back until the whole pool has cycled. -> {"src","alt"} or None."""
    P = pool().get(topic) or pool().get("world") or []
    if not P: return None
    im = P[issue_no(issue) % len(P)]
    try:
        if os.path.isdir(os.path.dirname(LOG)):
            import json
            lg = json.load(open(LOG)) if os.path.exists(LOG) else {}
            lg.setdefault(str(issue_no(issue)), {})[topic] = im["name"]
            json.dump(lg, open(LOG, "w"), indent=1)
    except Exception:
        pass
    return {"src": f"{V2._base(c)}/bnt/media/{im['name']}", "alt": "", "kind": "divider", "credit": None}

def _divider(topic, issue, c, first=False):
    im = pick(topic, issue, c)
    lab = (f'<div class="bnm" style="font:600 12px/18px {FACE};letter-spacing:2.4px;color:{MU}">{E(TOPIC_LABEL.get(topic, "World").upper())}</div>')
    out = _row(lab, ("8px" if first else "64px") + " 24px 16px 24px")
    if im:
        out += (f'<tr><td style="padding:0;background:{BG}"><img src="{E(im["src"])}" width="{W}" alt="" style="display:block;width:100%;max-width:{W}px;'
                f'height:auto;border:0;outline:none;background:{SURF}"></td></tr>')
    return out

def rank_col(rk):
    rk = max(0, min(10, int(rk or 0)))
    return RED if rk >= 7 else RANK_GREY.get(rk, "#E5E5EA")

def _rank_line(it, extra=()):
    N = _N(); parts = []
    if it.get("rank") is not None:
        rk = max(0, min(10, int(it.get("rank") or 0))); name = it.get("tier") or N.tier(rk)[0]
        parts.append(f'<span style="color:{rank_col(rk)};font-weight:700">RANK {rk}' + (f' &middot; {E(str(name).upper())}' if name else "") + '</span>')
    place = (it.get("where") or "").strip()
    if place and V2._place_named(place, it): parts.append(f'<span style="color:{MU}">{E(N._one_line(place, 34).upper())}</span>')
    if it.get("update"): parts.append(f'<span style="color:{TX}">UPDATE</span>')
    if it.get("editorial") or it.get("section") == "watchlist": parts.append(f'<span style="color:{MU}">UNCONFIRMED</span>')
    parts += list(extra)
    if not parts: return ""
    sep = f'<span style="color:{DIM}"> &nbsp;&middot;&nbsp; </span>'
    return f'<div style="font:600 12px/18px {FACE};letter-spacing:1.6px;margin:0 0 10px 0">{sep.join(parts)}</div>'

def _headline(text, big=False):
    sz = "30px/36px" if big else "22px/28px"
    return (f'<div class="bnt bnh1" data-bn-h="1" style="font:600 {sz} {FACE};letter-spacing:-0.3px;color:{TX};text-align:left;margin:0">'
            f'{E(text)}</div>')

def _summary(text):
    return f'<p class="bnx" style="margin:12px 0 0 0;font:400 16px/25px {FACE};color:{BODY};text-align:left">{E(text)}</p>'

def button(label, url):
    """Bulletproof outlined white button (monochrome, no fill)."""
    return ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:22px 0 0 0"><tr>'
            f'<td style="border:1px solid {TX};border-radius:999px;mso-padding-alt:12px 26px">'
            f'<a href="{E(url)}" class="bnt" style="display:inline-block;padding:13px 26px;font:600 14px/18px {FACE};letter-spacing:1.4px;'
            f'color:{TX};text-decoration:none;text-transform:uppercase;border-radius:999px">{E(label)}</a></td></tr></table>')

def _img(im, refs, full=False):
    cr = im.get("credit")
    if cr: refs.credit(cr["subject"], cr["kind"], cr["who"], cr["link"], cr["year"])   # credits list lives on /credits + text part
    w = W if full else W - 48
    return (f'<img src="{E(im["src"])}" width="{w}" alt="{E(im["alt"])}" style="display:block;width:100%;max-width:{w}px;height:auto;'
            f'border:0;outline:none;background:{SURF};color:{MU};font:400 14px/20px {FACE}">')

def _row(inner, pad="0 24px", bg=BG):
    return f'<tr><td class="bnpad" bgcolor="{bg}" style="padding:{pad};background:{bg};text-align:left">{inner}</td></tr>'

def _rule():
    return _row(f'<div style="height:1px;line-height:1px;font-size:0;background:{LINE}">&nbsp;</div>', "0 24px")

def _section(label):
    return _row(f'<div class="bnm" style="font:600 12px/18px {FACE};letter-spacing:2.4px;color:{MU}">{E(label.upper())}</div>', "48px 24px 0 24px")

def story(it, c, refs, lead=False, label="Read the full story", url=None, head=None, text=None, first=False, big=False):
    N = _N(); url = url or N.wire_url(it["cluster_id"], c=c); head = head or N.card_headline(it)
    s = text if text is not None else V2.summary(it)
    body = _rank_line(it) + _headline(head, big=big) + (_summary(s) if s else "")
    al = N.also_line(it)
    if al: body += _summary(al)
    body += button(label, url)
    if first: return _row(body, "30px 24px 0 24px")
    return _row(f'<div style="height:1px;line-height:1px;font-size:0;background:{LINE}">&nbsp;</div>', "36px 24px 0 24px") + _row(body, "30px 24px 0 24px")

def _masthead(issue, c):
    N = _N(); lab = N.slot_label(issue["slot"]); day = issue.get("label") or issue["end"].astimezone(N.ET).strftime("%A, %B %-d")
    return _row(f'<a href="{E(V2._base(c))}/" class="bnt" style="font:600 22px/26px {FACE};letter-spacing:-0.2px;color:{TX};text-decoration:none">{WORDMARK}</a>'
                f'<div class="bnm" style="font:400 13px/18px {FACE};letter-spacing:1.8px;color:{MU};margin:6px 0 0 0">{TAGLINE.upper()}</div>'
                f'<div class="bnm" style="font:400 13px/18px {FACE};letter-spacing:1.8px;color:{DIM};margin:22px 0 0 0">{E(lab.upper())} BRIEF &middot; {E(day.upper())}</div>',
                "36px 24px 28px 24px")

def _top_list(pool, first=False):
    if len(pool) < 2: return ""
    li = "".join(f'<tr><td valign="top" class="bnt" style="padding:14px 0;border-top:1px solid {LINE};font:400 16px/23px {FACE};color:{TX};text-align:left">'
                 f'<b style="font-weight:700">{i}. {E(_N().card_headline(it))}</b></td></tr>' for i, it in enumerate(pool, 1))
    return (_row(f'<div class="bnm" style="font:600 12px/18px {FACE};letter-spacing:2.4px;color:{MU}">RIGHT NOW</div>', "0 24px")
            + _row(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:14px 0 0 0">{li}</table>', "0 24px"))

def _line(title, url, meta):
    return _row(f'<a href="{E(url)}" class="bnt" style="display:block;padding:14px 0;border-top:1px solid {LINE};text-decoration:none">'
                f'<span style="display:block;font:500 16px/23px {FACE};color:{TX}">{E(title)}</span>'
                f'<span class="bnm" style="display:block;font:400 13px/19px {FACE};color:{MU};margin-top:4px">{meta}</span></a>', "0 24px")

def _footer(links, c, why):
    N = _N(); addr, addr_html = N._addr(c); L = V2._top_links(links); base = V2._base(c)
    F = f"font:400 12px/19px {FACE};color:{DIM}"
    lk = lambda lab, url: (f'<a href="{E(url)}" class="bnm" style="display:inline-block;padding:10px 18px 10px 0;font:500 13px/20px {FACE};'
                           f'color:{MU};text-decoration:underline">{lab}</a>')
    ctl = [("Live site", base + "/"), ("How we score", L["scoring"]), ("Image credits", base + "/credits"), ("Forward to a friend", N.FORWARD_URL)]
    ctl2 = [("Manage subscription", L.get("categories") or L.get("manage")), ("Sources", L.get("sources") or L.get("site"))]
    if L.get("stop_tracking"): ctl2.append(("Stop tracking my opens and clicks", L["stop_tracking"]))
    ctl2.append(("Unsubscribe (one click)", L["unsubscribe"]))
    if L.get("breaking_off"): ctl2.append(("Stop breaking alerts", L["breaking_off"]))
    return ('<!--bn-footer-->' + _row(f'<div style="height:1px;line-height:1px;font-size:0;background:{LINE}">&nbsp;</div>', "64px 24px 0 24px")
            + _row(f'<div class="bnt" style="font:600 18px/22px {FACE};color:{TX}">{WORDMARK}</div>'
                   f'<div class="bnm" style="font:400 12px/18px {FACE};letter-spacing:1.6px;color:{MU};margin:4px 0 18px 0">{TAGLINE.upper()}</div>'
                   + "".join(lk(a, b) for a, b in ctl) + '<br>' + "".join(lk(a, b) for a, b in ctl2 if b), "26px 24px 0 24px")
            + _row(f'<p class="bnm" style="margin:0 0 8px 0;{F}">{E(N.DISCLAIMER)}</p><p class="bnm" style="margin:0 0 8px 0;{F}">{E(why)}</p>'
                   f'<p class="bnm" style="margin:0;{F}">{N.BRAND} &middot; {addr_html}</p>', "18px 24px 40px 24px"))

CSS = (":root{color-scheme:dark only;supported-color-schemes:dark}"
       f"body,.bnb{{background:{BG}!important;color:{TX}!important}}.bnt{{color:{TX}!important}}.bnm{{color:{MU}!important}}.bnx{{color:{BODY}!important}}"
       "@media (prefers-color-scheme: light){"
       f"body,.bnb{{background:{BG}!important;color:{TX}!important}}.bnt{{color:{TX}!important}}.bnm{{color:{MU}!important}}.bnx{{color:{BODY}!important}}}}"
       f"[data-ogsc] .bnt{{color:{TX}!important}}[data-ogsb] .bnb{{background:{BG}!important}}"
       "a[x-apple-data-detectors]{color:inherit!important;text-decoration:none!important}"
       "u + .body .bnb{background:#000!important}"
       "@media only screen and (max-width:480px){.bnh1{font-size:22px!important;line-height:28px!important}"
       ".bnlead .bnh1{font-size:27px!important;line-height:33px!important}.bnpad{padding-left:20px!important;padding-right:20px!important}}")

def _head(title):
    return ('<!DOCTYPE html><html lang="en" xmlns="http://www.w3.org/1999/xhtml"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="x-apple-disable-message-reformatting"><meta name="color-scheme" content="dark only"><meta name="supported-color-schemes" content="dark only">'
            f'<title>{E(title)}</title><style>{CSS}</style></head>')

def render(issue, links, c):
    """-> (subject, html, text), same contract as newsletter.render."""
    N = _N(); subj = N.subject_for(issue); camp = f"{issue.get('slot') or 'brief'}-{issue['end'].astimezone(N.ET).strftime('%Y-%m-%d')}"
    N._number_map(issue)
    refs = V2.Refs(); B = [_masthead(issue, c)]
    items = V2._story_items(issue)
    top = V2.top_stories(issue, 3)
    seen = set()
    B.append(_top_list(top, first=True))
    for lab, key in ((f"Near you &middot; {issue.get('loc_label') or 'your area'}", "near"), ("Stories you follow", "follow")):
        if issue.get(key):
            B.append(_row(f'<div class="bnm" style="font:600 12px/18px {FACE};letter-spacing:2.4px;color:{MU}">{lab.upper()}</div>', "48px 24px 0 24px"))
            for it in issue[key]:
                if it.get("cluster_id") in seen: continue
                seen.add(it.get("cluster_id")); B.append(story(it, c, refs))
    feats = []
    for f_ in issue.get("featured") or []:
        feats.append(dict({"cluster_id": f_["cluster_id"], "title": f_["title"], "display_title": f_["title"], "rank": None, "where": "",
                           "category": f_.get("category")}, _feat=f_))
    groups = V2.grouped(issue, [it for it in items if it.get("cluster_id") not in seen] + feats)
    if not groups:
        B.append(_row(_headline(N.MATTERS) + _summary("A quiet window: nothing new passed our brief gate.") + button("Open the live site", V2._base(c) + "/"), "24px 24px 0 24px"))
    for gi, (g, its) in enumerate(groups):
        B.append(_divider(g, issue, c))
        for k, it in enumerate(its):
            seen.add(it.get("cluster_id")); f_ = it.get("_feat")
            if f_: B.append(story(it, c, refs, url=f_["url"], head=f_["title"], text=f_.get("text") or "", first=k == 0, big=gi == 0 and k == 0))
            else: B.append(story(it, c, refs, first=k == 0, big=gi == 0 and k == 0))
    if issue.get("crime"):
        cr = issue["crime"]
        B.append(_section(f"Crime near you · {cr['label']}"))
        B.append(_row("".join(_summary(x) for x in cr["lines"][:3]) + button("See the numbers", cr["url"]), "14px 24px 0 24px"))
    others = [it for it in issue.get("developing") or [] if not it.get("lead") and it.get("cluster_id") not in seen]
    if others or issue.get("watchlist"):
        B.append(_section("Also on the wire"))   # short list, no divider image
        B.append('<tr><td style="font-size:0;line-height:14px;height:14px">&nbsp;</td></tr>')
        for it in others:
            rk = int(it.get("rank") or 0)
            B.append(_line(N._cut(it["title"], 140), N.wire_url(it["cluster_id"], c=c),
                           f'<span style="color:{rank_col(rk)}">Rank {rk}</span> &middot; first logged {E(N.fmt_et(it.get("first_seen")))}'))
        for it in issue.get("watchlist") or []:
            B.append(_line(N._cut(it["title"], 140), N.wire_url(it["cluster_id"], c=c), f'Unconfirmed &middot; {E(N.fmt_et(it.get("first_seen")))}'))
    why = f"You get this because you confirmed a subscription to the {N.BRAND} newsletter. Change how often it arrives, or turn off breaking alerts, under Manage subscription."
    pool = N._story_pool(issue)
    pre = (N.card_headline(pool[0]) + (f" + {len(pool) - 1} more." if len(pool) > 1 else "")) if pool else N.MATTERS
    html_ = (_head(subj) + f'<body bgcolor="{BG}" class="bnb body" style="margin:0;padding:0;background:{BG};color:{TX};-webkit-text-size-adjust:100%">'
             f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{BG}">{E(pre)}&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;</div>'
             f'<table role="presentation" class="bnb" bgcolor="{BG}" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG}"><tr><td bgcolor="{BG}" align="center" style="padding:0;background:{BG}">'
             '<!--[if mso]><table role="presentation" width="600" align="center" cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->'
             f'<table role="presentation" class="bnb" bgcolor="{BG}" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:{W}px;background:{BG};font-family:{FACE};color:{TX};text-align:left">'
             + "".join(x for x in B if x) + _footer(links, c, why) + '</table><!--[if mso]></td></tr></table><![endif]--></td></tr></table></body></html>')
    text = V2.text_part(issue, links, c, subj, why, None, None, refs).replace(N.TAGLINE, TAGLINE)
    text = text.replace(f"{N.BRAND} · {TAGLINE}", f"{WORDMARK} · {TAGLINE}") + f"\nImage credits: {V2._base(c)}/credits\n"
    return (subj,) + N.utm_tag(html_, text, camp)
