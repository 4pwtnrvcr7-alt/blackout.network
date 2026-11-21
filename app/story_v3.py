"""Story v3: full narrative pages for /wire/<cluster_id>, on by default (BN_STORY_V3=0 turns it off).

When the flag is on, Wire v2 story pages open on a full-screen hero (looping video on
desktop, still on phones and reduced-motion), a headline and dek, then What happened,
Background, Analysis and What to watch — human prose only. Confidence and rank sit in a
compact block lower on the page, with "How we rank" behind an expand. Image credits live
on /credits#stories, never on the images.

Desk content comes from an optional `story` object on a brief (headline, dek, sections,
hero, images), falling back to the existing v2 brief fields, then to an honest thin page
built only from the scanner's reports. Nothing is invented.
"""
from __future__ import annotations
import html, json, os, re
from datetime import datetime, timezone, timedelta

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
ST_CSS = "/wire2/static/story3.css?v=2"
ST_IMG = "/wire2/static/img"
ST_VID = "/wire2/static/vid"
FLAG = "BN_STORY_V3"
OFFICIAL_HINTS = (
    "who", "cdc", "ecdc", "unicef", "gdacs", "imd", "noaa", "nasa", "usgs", "fema",
    "un ", "un.", "united nations", "federal reserve", "federalreserve", "africacdc",
    "africa cdc", "africa cdc", "jtwc", "wmo", "nhs", "nih", "fda", "gov.",
)

def on():
    """On by default (Matt approved, Nov 17 2026). Rollback: Render env BN_STORY_V3=0."""
    return os.environ.get(FLAG, "").strip() != "0"

# ---------------------------------------------------------------- data
def _paths():
    here = os.path.dirname(os.path.abspath(__file__))
    env = os.environ.get("BN_STORY_V3_BRIEFS", "").strip()
    out = []
    if env: out.append(env)
    out.append(os.path.join(here, "data", "story_v3_briefs.json"))
    return out

_BR = {"mt": None, "v": {}}

def _load_v3():
    """Prefers BN_STORY_V3_BRIEFS / app/data/story_v3_briefs.json (full stories)."""
    for p in _paths():
        if not p or not os.path.isfile(p): continue
        try:
            mt = os.path.getmtime(p)
            if _BR["mt"] == (p, mt): return _BR["v"]
            d = json.load(open(p))
            briefs = d.get("briefs") if isinstance(d, dict) and isinstance(d.get("briefs"), dict) else (d if isinstance(d, dict) else {})
            _BR["mt"], _BR["v"] = (p, mt), briefs
            return briefs
        except Exception:
            continue
    return {}

def _desk_note(cid):
    """Existing desk brief / newsletter note from story_reports.json, if any."""
    try:
        import story_report as SR
        rec = (SR.reports() or {}).get("notes") or {}
        n = rec.get(cid)
        return n if isinstance(n, dict) else None
    except Exception:
        return None

def note_for(cid):
    """v3 brief (with optional story) wins; else the pushed desk note."""
    v3 = _load_v3().get(cid)
    if isinstance(v3, dict): return v3
    d = _desk_note(cid)
    if d: return d
    try:   # Nov 21 2026 (Matt): instant API write-up (story_writer.py), only when the desk has nothing for this story
        import story_writer as SW
        return SW.note_for(cid)
    except Exception:
        return None

# ---------------------------------------------------------------- prose helpers
def paras(text):
    text = (text or "").strip()
    if not text: return ""
    chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
    if len(chunks) == 1:
        # also split a long single block into paragraphs on sentence groups of 2–3
        chunks = [text]
    return "".join(f"<p>{E(c)}</p>" for c in chunks)

def official_families(fams):
    out = []
    for f in fams or []:
        s = str(f).strip()
        if not s or s.lower() == "social": continue
        low = s.lower()
        if any(h in low for h in OFFICIAL_HINTS) or low in {"who", "cdc", "un", "imd", "jtwc"}:
            out.append(s)
    return out

def human_sources_line(it, note):
    """Plain-language confidence, never scoring jargon."""
    fams = [f for f in (it.get("families") or []) if str(f).lower() != "social"]
    official = official_families(fams)
    n_fam = it.get("n_families") or len(fams) or 0
    conf = (note or {}).get("confidence") or ""
    why = (note or {}).get("confidence_why") or ""
    bits = []
    if conf in ("High", "Medium", "Low"):
        bits.append(f"Our confidence is {conf.lower()}.")
    if why:
        bits.append(why.rstrip(".") + ".")
    else:
        if official:
            bits.append("Official sources in the record include " +
                        (", ".join(official[:4]) + ("." if len(official) <= 4 else " and others.")))
        elif n_fam:
            bits.append(f"The reports we have come from {n_fam} independent source{'s' if n_fam != 1 else ''}.")
        else:
            bits.append("We are working from the reports logged on this page.")
    return " ".join(bits)

_JARGON = re.compile(
    r"\b(?:severity\s*\d+\s*/\s*100|rank\s*\d+\s*/\s*10|item\(s\)|source family|eff_families|"
    r"n_items|n_families|score\s*\d+)\b",
    re.I,
)

def strip_jargon(s):
    s = _JARGON.sub("", s or "")
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\s+([,;])", r"\1", s)
    s = re.sub(r"\s+\.", ".", s)
    return s.strip()

def assemble(note, it, W):
    """Build headline, dek and sections from story.*, else v2 brief fields, else scanner."""
    story = (note or {}).get("story") if isinstance((note or {}).get("story"), dict) else {}
    secs = story.get("sections") if isinstance(story.get("sections"), dict) else {}
    title = it.get("title") or ""
    h = (story.get("headline") or (note or {}).get("headline") or W.headline(title) or title).strip()
    dek = (story.get("dek") or (note or {}).get("why_it_matters") or "").strip()
    happened = (secs.get("happened") or (note or {}).get("what_happened") or "").strip()
    background = (secs.get("background") or "").strip()
    analysis = (secs.get("analysis") or "").strip()
    if not analysis:
        analysis = "\n\n".join(x for x in [(note or {}).get("analysis") or "", (note or {}).get("rank_why") or ""] if x)
    watch = (secs.get("watch") or "").strip()
    if not watch:
        watch = "\n\n".join(x for x in [
            (note or {}).get("if_true") or (note or {}).get("outlook") or "",
            (note or {}).get("if_false") or "",
            (note or {}).get("what_to_do") or "",
        ] if x)
    def _norm(s):
        return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
    # scanner fallback for happened — only if it adds facts beyond the headline
    if not happened:
        p = W.brief_parts(it.get("brief"))
        what = strip_jargon(p.get("what") or "")
        if what and _norm(what) and _norm(what) != _norm(title) and _norm(what) not in _norm(title) and _norm(title) not in _norm(what):
            happened = what
        else:
            happened = ""  # stay honest; the page will say we have not written this up yet
    if not dek:
        dek = strip_jargon((W.dek_for(it, h) or "").strip())
        # avoid repeating the headline or a source-count line as if it were a dek we wrote
        if (not dek) or _norm(dek) == _norm(h) or _norm(dek) == _norm(title) or re.search(r"independent source|reports$", dek, re.I):
            dek = W.first_sentence(happened, 140) if happened else ""
    hero = story.get("hero") if isinstance(story.get("hero"), dict) else {}
    images = story.get("images") if isinstance(story.get("images"), list) else []
    written = story.get("written_at") or (note or {}).get("written_at") or (note or {}).get("generated_at") or ""
    return {
        "headline": h, "dek": dek, "happened": happened, "background": background,
        "analysis": analysis, "watch": watch, "hero": hero, "images": images,
        "written": written, "has_desk": bool(note and (note.get("what_happened") or secs)),
    }

# ---------------------------------------------------------------- images / hero
def hero_html(hero, it, W):
    """Full-screen hero: looping video on desktop, still on phones / reduced motion."""
    # default stills from Wire v2 catalogue when the desk did not pick a hero
    img = (hero or {}).get("image") or ""
    img_m = (hero or {}).get("image_mobile") or ""
    video = (hero or {}).get("video") or ""
    alt = (hero or {}).get("alt") or ""
    if not img:
        used = W.Used()
        k = used.take(W.img_keys(it)) or used.take(["night"])
        if k:
            img = f"{ST_IMG}/{W.IMG[k][0]}"
            m = W.IMG[k][0].replace(".webp", "_m.webp")
            if os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "wire_v2_static", "img", m + ".b64")) or \
               os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "wire_v2_static", "img", m)):
                img_m = f"{ST_IMG}/{m}"
    sources = ""
    if img_m:
        sources = f'<source media="(max-width: 700px)" srcset="{E(img_m)}">'
    vid = ""
    if video:
        poster = img or ""
        vid = (f'<video class="sv3-vid" autoplay muted loop playsinline preload="metadata" '
               f'poster="{E(poster)}" aria-hidden="true"><source src="{E(video)}" type="video/mp4"></video>')
    still = f'<picture>{sources}<img class="sv3-still" src="{E(img)}" alt="{E(alt)}" decoding="async" fetchpriority="high"></picture>' if img else ""
    return f'<div class="sv3-hi">{vid}{still}</div>'

def inline_figures(images, skip_hero=True):
    out = []
    for im in images or []:
        if not isinstance(im, dict): continue
        role = (im.get("role") or "inline").lower()
        if skip_hero and role == "hero": continue
        src = im.get("src") or ""
        if not src: continue
        alt = im.get("alt") or ""
        out.append(f'<figure class="sv3-fig"><img src="{E(src)}" alt="{E(alt)}" loading="lazy" decoding="async"></figure>')
    return "".join(out)

# ---------------------------------------------------------------- render
def _sources_list(note, it):
    seen, rows = set(), []
    def add(url, label):
        url = (url or "").strip()
        if not url.startswith("http") or url in seen: return
        seen.add(url)
        host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url).split("/")[0])
        rows.append((url, label or host))
    # desk sources first (may be url strings or {url, domain})
    for s in ((note or {}).get("sources") or []):
        if isinstance(s, str): add(s, "")
        elif isinstance(s, dict): add(s.get("url"), s.get("domain") or s.get("title") or "")
    story = (note or {}).get("story") if isinstance((note or {}).get("story"), dict) else {}
    for s in (story.get("sources") or []):
        if isinstance(s, str): add(s, "")
        elif isinstance(s, dict): add(s.get("url"), s.get("label") or s.get("title") or "")
    for l in (it.get("links") or []):
        if not isinstance(l, dict): continue
        url = str(l.get("url") or "")
        lab = l.get("source") or ""
        # skip social when we already have official links
        if re.search(r"bsky\.app|twitter\.com|x\.com/|mastodon\.", url, re.I) and rows:
            continue
        add(url, lab)
    return rows

def render(state, cid):
    """Full HTML page, or None if the cluster is not on the board (caller falls back)."""
    import wire_v2 as W
    m = W.items(state)
    it = next((x for x in m + (state.get("watchlist") or []) if x.get("cluster_id") == cid), None)
    if not it: return None
    note = note_for(cid)
    a = assemble(note, it, W)
    r = int(it.get("rank") or 0)
    cat = (it.get("category") or "").upper()
    written = ""
    if a["written"]:
        try:
            written = "Desk brief " + W.et(a["written"])
        except Exception:
            written = ""
    meta_bits = [x for x in [
        f"Seen {W.et(it.get('first_seen'))}" if it.get("first_seen") else "",
        f"Updated {W.et(it.get('updated'))}" if it.get("updated") else "",
        written,
    ] if x]
    body = ['<article class="sv3">',
            '<section class="sv3-hero">',
            hero_html(a["hero"], it, W),
            '<div class="sv3-hc">',
            f'<p class="sv3-eb"><a href="/wire">THE WIRE</a> / {E(cat or "STORY")}</p>',
            f'<h1 class="sv3-h">{E(a["headline"])}</h1>',
            (f'<p class="sv3-dek">{E(a["dek"])}</p>' if a["dek"] else ""),
            (f'<p class="sv3-meta">{E(" · ".join(meta_bits))}</p>' if meta_bits else ""),
            '</div></section>']
    # narrative
    if a["happened"]:
        body.append('<section class="sv3-sec" id="happened"><div class="sv3-wrap">'
                    '<p class="sv3-eb">What happened</p>'
                    f'<div class="sv3-prose">{paras(a["happened"])}</div></div></section>')
    elif not a["has_desk"]:
        body.append('<section class="sv3-sec" id="happened"><div class="sv3-wrap">'
                    '<p class="sv3-eb">What happened</p>'
                    '<div class="sv3-prose"><p>We have not yet written this story up. Below is what the reports we track actually say, without adding claims we cannot source.</p></div>'
                    '</div></section>')
    figs = inline_figures(a["images"])
    if figs:
        body.append(f'<section class="sv3-sec sv3-sec-fig"><div class="sv3-wrap sv3-wrap-wide">{figs}</div></section>')
    if a["background"]:
        body.append('<section class="sv3-sec" id="background"><div class="sv3-wrap">'
                    '<p class="sv3-eb">Background and history</p>'
                    f'<div class="sv3-prose">{paras(a["background"])}</div></div></section>')
    if a["analysis"]:
        body.append('<section class="sv3-sec" id="analysis"><div class="sv3-wrap">'
                    '<p class="sv3-eb">Our analysis</p>'
                    f'<div class="sv3-prose">{paras(a["analysis"])}</div></div></section>')
    if a["watch"]:
        body.append('<section class="sv3-sec" id="watch"><div class="sv3-wrap">'
                    '<p class="sv3-eb">What to watch next</p>'
                    f'<div class="sv3-prose">{paras(a["watch"])}</div></div></section>')
    srcs = _sources_list(note, it)
    if srcs:
        lis = "".join(f'<li><a href="{E(u)}" rel="noopener nofollow" target="_blank">{E(lab)}</a></li>' for u, lab in srcs)
        body.append('<section class="sv3-sec" id="sources"><div class="sv3-wrap">'
                    '<p class="sv3-eb">Sources</p>'
                    f'<ol class="sv3-src">{lis}</ol>'
                    '</div></section>')
    # compact confidence + rank, lower on the page
    conf_line = human_sources_line(it, note)
    risk = (note or {}).get("risk") or ""
    risk_why = (note or {}).get("risk_why") or ""
    risk_html = ""
    if risk in ("Low", "Medium", "High"):
        risk_html = f'<p class="sv3-risk">Our read of the risk to a general reader is {E(risk.lower())}' + (f' — {E(risk_why)}' if risk_why else ".") + "</p>"
    body.append(
        '<section class="sv3-sec sv3-assess" id="assessment"><div class="sv3-wrap">'
        '<p class="sv3-eb">Confidence and rank</p>'
        f'{W.rank_block(r, True)}'
        f'<p class="sv3-conf">{E(conf_line)}</p>'
        + risk_html +
        '<details class="sv3-acc"><summary>How we rank</summary>'
        '<p>Ranks run from 0 to 10 and follow published scoring rules, including how widely a story reaches and how many independent sources report it. A high rank is not the same as a high risk to you. <a href="/scoring">How we score →</a></p>'
        '</details>'
        f'<div class="sv3-share">{W.btn(f"https://x.com/intent/post?text={E(a["headline"])}&url=https://blackout.network/wire/{E(cid)}", "Post on X", "w2-btn-s")}'
        '<button type="button" class="w2-btn w2-btn-s" data-copy>Copy link</button></div>'
        '<p class="sv3-cred"><a href="/credits#stories">Image credits</a></p>'
        '</div></section>'
    )
    nxt = [x for x in m if x.get("cluster_id") != cid][:3]
    if nxt:
        rows = "".join(
            f'<article class="w2-row">{W.rank_block(x.get("rank"))}<div class="w2-rb">'
            f'<p class="w2-eb">{E((x.get("category") or "").upper())}</p>'
            f'<h3 class="w2-rh"><a href="/wire/{E(x["cluster_id"])}">{E(W.headline(x.get("title")))}</a></h3>'
            f'<p class="w2-meta">{E(W.ago(x.get("updated")))}</p></div></article>'
            for x in nxt)
        body.append('<section class="sv3-sec"><div class="sv3-wrap sv3-wrap-wide">'
                    f'<p class="sv3-eb">More on The Wire</p><div class="w2-rows">{rows}</div>'
                    f'<div class="w2-morew">{W.btn("/wire", "All stories")}</div></div></section>')
    body.append("</article>")
    html_out = W.shell(f"{a['headline']} | BLACKOUT.NETWORK", a["dek"] or W.first_sentence(it.get("title") or "", 150),
                       "".join(body), f"/wire/{cid}", rank=r)
    html_out = re.sub(r'(wire2\.css\?v=\d+">)', lambda m: m.group(1) + '<link rel="stylesheet" href="' + ST_CSS + '">', html_out, count=1)   # any wire2.css version
    html_out = html_out.replace('<body class="w2">', '<body class="w2 sv3">')
    # no snap on story pages even if a later shared stylesheet adds it
    html_out = html_out.replace('<body class="w2 sv3">', '<body class="w2 sv3" data-sv3="1" style="scroll-snap-type:none">')
    return html_out
