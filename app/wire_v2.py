"""Wire v2 (preview, Nov 17 2026): SpaceX-language rebuild of /wire and /wire/<id>, plus the new full-screen menu.

Dispatched from story.handle_get (/wire, /wire/<id>) and addons ROUTES (/wire2/static). BN_WIRE_V2=0 turns it off.
Data: the same dict /api/state returns (read-only). Images: wire_v2_static/img (see IMAGE_LEDGER in the preview folder).
"""
import html, json, os, re, time
from datetime import datetime, timezone, timedelta

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
ON = os.environ.get("BN_WIRE_V2", "1") != "0"   # Push F: on by default; BN_WIRE_V2=0 = old /wire + story pages
ST = "/wire2/static"
RANK_NAMES = {0: "Noise", 1: "Low", 2: "Low", 3: "Minor", 4: "Elevated", 5: "Notable", 6: "Serious",
              7: "Major", 8: "Severe", 9: "Critical", 10: "Catastrophic"}

# ---------------------------------------------------------------- images (one use per view; relevance first, else no photo)
IMG = {
    "list_hero": ("iss070e062746.webp", "Image: NASA"),
    "cyclone":   ("iss063e057876.webp", "Illustrative: a tropical cyclone seen from the ISS (NASA, 2020). Not this storm."),
    "cyclone2":  ("iss057e023128.webp", "Illustrative: a hurricane seen from the ISS (NASA, 2018). Not this storm."),
    "night":     ("iss067e302248.webp", "Image: NASA"),
    "health":    ("gen_health_abstract.webp", "Graphic: BLACKOUT.NETWORK"),
    "geo":       ("gen_geo_lines.webp", "Graphic: BLACKOUT.NETWORK"),
    "signal":    ("gen_signal_lines.webp", "Graphic: BLACKOUT.NETWORK"),
}
def credit_html(k):
    """Matt 12:07 PM: no source credits on images (they live on /credits, linked from every page footer). BN_CREDITS_PAGE=0 = old overlays."""
    import os as _o
    if _o.environ.get("BN_CREDITS_PAGE", "1") == "0": return f'<p class="w2-credit">{E(IMG[k][1])}</p>'
    return ""  # Matt 1:19 PM: no labels on photos at all; the illustrative note lives on /credits#wire
CYC = re.compile(r"\b(tropical cyclone|cyclone|hurricane|typhoon|tropical storm)\b", re.I)

def img_keys(it):
    """Candidate images for a story, most relevant first. Empty list = use the line-art graphic, never a misleading photo."""
    cat = (it.get("category") or "").lower(); t = it.get("title") or ""
    if CYC.search(t): return ["cyclone", "cyclone2"]
    if cat == "disease": return ["health"]
    if cat in ("political", "war/conflict"): return ["geo"]
    if cat in ("financial", "cyber"): return ["signal"]
    if cat == "natural disaster" and re.search(r"\b(earthquake|quake|tsunami|volcan)", t, re.I): return ["geo"]
    return []

class Used:
    def __init__(self): self.s = set()
    def take(self, keys):
        for k in keys:
            if k not in self.s: self.s.add(k); return k
        return None

# ---------------------------------------------------------------- text helpers
def headline(t):
    try:
        import theme; h = theme._headline(t or "")
    except Exception: h = t or ""
    h = (h or t or "").strip()
    if len(h) > 84:
        m = re.match(r"^(.{20,84}?[.!?])\s", h)
        h = m.group(1).rstrip(".") if m else h[:84].rsplit(" ", 1)[0].rstrip(",;:-— ") + "…"
    return h

def brief_parts(b):
    b = b or ""; out = {}
    for k in ("WHAT", "WHERE", "WHEN", "CONFIDENCE", "VERIFY"):
        m = re.search(k + r":\s*(.+?)(?=\s+(?:WHAT|WHERE|WHEN|CONFIDENCE|VERIFY):|$)", b, re.S)
        if m: out[k.lower()] = m.group(1).strip()
    if not out and b: out["what"] = b.strip()
    return out

def first_sentence(s, n=120):
    s = re.sub(r"\[[^\]]*\]", "", s or "").strip()
    m = re.match(r"^(.{25,%d}?[.!?])(\s|$)" % n, s)
    if m: return m.group(1)
    return (s[:n].rsplit(" ", 1)[0] + "…") if len(s) > n else s

def dek_for(it, h):
    """One short line under a headline that adds something: the report's first sentence if it is not just the headline again, else place + sourcing."""
    p = brief_parts(it.get("brief")); w = first_sentence(p.get("what") or "", 120)
    norm = lambda x: re.sub(r"[^a-z0-9]+", " ", (x or "").lower()).strip()
    ww = set(norm(w).split()); hw = set(norm(h).split())
    if w and len(w) > 30 and len(ww - hw) >= max(4, len(ww) // 2): return w   # adds real information beyond the headline
    nf = it.get("n_families") or 1
    return " · ".join(x for x in [it.get("location") or "", f"{nf} independent source" + ("s" if nf != 1 else ""), f"{it.get('n_items') or 0} reports"] if x)

def et(ts):
    if not ts: return ""
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
        l = d.astimezone(timezone(timedelta(hours=-5)))
        return l.strftime("%b %-d, %-I:%M %p") + " ET"
    except Exception: return str(ts)[:16]

def ago(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
        m = int((datetime.now(timezone.utc) - d).total_seconds() // 60)
        return f"{m} min ago" if m < 60 else (f"{m // 60} h ago" if m < 1440 else f"{m // 1440} d ago")
    except Exception: return ""

# ---------------------------------------------------------------- graphics (inline SVG, original)
def rank_ticks(r, big=False):
    """10-tick scale: ticks up to the rank are brighter and taller; red only for 7+ (option A of RANK_OPTIONS)."""
    r = int(r or 0); w, h = (150, 22) if big else (100, 14); gap = w / 10
    col = "#E5484D" if r >= 7 else "#FFFFFF"
    ticks = "".join(
        f'<rect x="{i * gap:.1f}" y="{0 if i < r else h * 0.45:.1f}" width="{1.5 if big else 1.2}" height="{h if i < r else h * 0.55:.1f}" '
        f'fill="{col if i < r else "#FFFFFF"}" opacity="{(0.45 + 0.055 * i) if i < r else 0.18:.2f}"/>' for i in range(10))
    return f'<svg class="w2-ticks" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true">{ticks}</svg>'

def rank_block(r, big=False):
    r = int(r or 0); hot = " w2-hot" if r >= 7 else ""
    return (f'<div class="w2-rank{hot}{" w2-rank-big" if big else ""}" aria-label="Rank {r} of 10, {RANK_NAMES.get(r, "")}">'
            f'<span class="w2-rn">{r}</span><span class="w2-rk"><span class="w2-rl">{E(RANK_NAMES.get(r, "").upper())}</span>{rank_ticks(r, big)}</span></div>')

def sources_graphic(n_fam, fams):
    """Independent source families as nodes converging on one point: replaces the old Signal snapshot bar."""
    n = max(1, min(int(n_fam or 1), 8)); W, H = 560, 150; cx, cy = W - 60, H / 2
    X0 = 200; pts = [(X0, 18 + i * ((H - 36) / max(1, n - 1)) if n > 1 else H / 2) for i in range(n)]
    lines = "".join(f'<path d="M{x},{y:.1f} C{W*0.45:.0f},{y:.1f} {W*0.6:.0f},{cy:.1f} {cx},{cy:.1f}" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="1"/>' for x, y in pts)
    dots = "".join(f'<circle cx="{x}" cy="{y:.1f}" r="3" fill="#fff"/>' for x, y in pts)
    labels = "".join(f'<text x="{X0 - 14}" y="{y + 4:.1f}" text-anchor="end" fill="#9AA0A8" font-size="11" letter-spacing="1.2">{E((lambda t: t if len(t) <= 20 else t[:19] + "…")(str(f).upper()))}</text>' for (x, y), f in zip(pts, (fams or [])[:n]))
    return (f'<svg class="w2-srcg" viewBox="0 0 {W} {H}" role="img" aria-label="{n} independent source families">{lines}{dots}{labels}'
            f'<circle cx="{cx}" cy="{cy}" r="7" fill="none" stroke="#fff"/><circle cx="{cx}" cy="{cy}" r="2.5" fill="#fff"/>'
            + (f'<text x="{cx}" y="{cy + 26}" text-anchor="middle" fill="#9AA0A8" font-size="11" letter-spacing="1.2">+{int(n_fam) - n} MORE</text>' if int(n_fam or 0) > n else "") + '</svg>')

# ---------------------------------------------------------------- shell: minimal bar + full-screen menu
def menu_html():
    groups = []
    try:
        import sitenav_ui as U
        import sitenav as SN
        for sid, name, desc, rows in U.menu3_sections(SN):
            links = [(lab, href) for key, lab, href in rows if href][:7]
            if links: groups.append((name, links))
    except Exception:
        groups = [("Latest", [("The Wire", "/wire"), ("Live", "/live"), ("Map", "/map")])]
    cols = "".join(f'<div class="w2-mg"><p class="w2-mgl">{E(n)}</p><ul>' + "".join(f'<li><a href="{E(h)}">{E(l)}</a></li>' for l, h in links) + '</ul></div>' for n, links in groups)
    try:   # Nov 24 2026 (Matt): menu v5 body (menu5.py); deactivated pages are gone from it
        import menu5, deactivated
        if menu5.on():
            foot = "".join(f'<a href="{h}">{t}</a>' for h, t in (("/scoring", "How we score"), ("/sources", "Sources"), ("/privacy", "Privacy"), ("/tos", "Terms")) if not deactivated.is_off(h))
            return ('<div class="w2-menu" id="w2_menu" role="dialog" aria-modal="true" aria-label="Site menu" hidden>'
                    '<div class="w2-mtop"><a class="w2-wm" href="/?intro=1">blackout.network</a><button type="button" class="w2-close" id="w2_close" aria-label="Close menu">CLOSE<i></i></button></div>'
                    '<nav class="w2-mnav w2-m5" aria-label="Site">' + menu5.html_block("/wire") + '</nav>'
                    '<div class="w2-mfoot">' + foot + '</div></div>')
    except Exception:
        import traceback; traceback.print_exc()
    return ('<div class="w2-menu" id="w2_menu" role="dialog" aria-modal="true" aria-label="Site menu" hidden>'
            '<div class="w2-mtop"><a class="w2-wm" href="/?intro=1">blackout.network</a><button type="button" class="w2-close" id="w2_close" aria-label="Close menu">CLOSE<i></i></button></div>'
            '<nav class="w2-mnav"><div class="w2-mlead"><a href="/?intro=1">Intro</a><a href="/wire">The Wire</a><a href="/live">Live</a><a href="/newsletter">Newsletter</a></div>'
            f'<div class="w2-mgrid">{cols}</div></nav>'
            '<div class="w2-mfoot"><a href="/scoring">How we score</a><a href="/sources">Sources</a><a href="/privacy">Privacy</a><a href="/tos">Terms</a>'
            '<a href="https://x.com/BlkoutNtw" rel="noopener" target="_blank">X</a><a href="https://www.youtube.com/@blkoutntw" rel="noopener" target="_blank">YouTube</a></div></div>')

def shell(title, desc, body, path, rank=None, noindex=False):
    try:
        import og, re as _re
        m = _re.match(r"/wire/([0-9a-f]{16})", path or "")
        if m:
            meta = og.tags(title=title, desc=desc, url="https://blackout.network" + path,
                           story_id=m.group(1), rank=rank, og_type="article")
        else:
            meta = og.tags(title=title, desc=desc, url="https://blackout.network" + path,
                           key="wire", og_type="website")
    except Exception:
        meta = ""
    robots = '<meta name="robots" content="noindex,nofollow,noarchive">' if noindex else ""
    return f'''<!doctype html><html lang="en" data-bnt-home data-bn-w2><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="https://blackout.network{E(path)}">
{robots}{meta}<meta name="theme-color" content="#000"><!-- w2: own design system; server.pwa_head skips the shared theme layer when it sees /bnt/theme.css here --><link rel="stylesheet" href="{ST}/wire2.css?v=7"></head>
<body class="w2"><header class="w2-bar" id="w2_bar"><a class="w2-wm" href="/?intro=1" aria-label="BLACKOUT.NETWORK intro">blackout.network</a>
<button type="button" class="w2-mbtn" id="w2_open" aria-label="Open menu" aria-controls="w2_menu" aria-expanded="false"><span class="bn-hx" aria-hidden="true"><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span></span><span class="bn-bl"><span class="bn-bl-a">Menu</span><span class="bn-bl-b">Close</span></span></button></header>
{menu_html()}<main id="w2_main">{body}</main>
<footer class="w2-foot"><p class="w2-tag">Global threat monitoring</p><p class="w2-legal">Independent early-warning signals. Not an official alert service. <a href="/scoring">How we score</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a></p></footer>
<script src="{ST}/wire2.js?v=3" defer></script></body></html>'''

def srcset(f):   # Push F: portrait mobile crop (wire_v2_static/img/*_m.webp, 720x1280) for phones
    m = f.replace(".webp", "_m.webp")
    if not os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "wire_v2_static", "img", m + ".b64")): return ""
    return f'<source media="(max-width: 700px)" srcset="{ST}/img/{m}">'

def hero(img_key, eyebrow, title, line, btn=None, cls="", h1=True, credit=True):
    f, cr = IMG[img_key]; tag = "h1" if h1 else "h2"
    return (f'<section class="w2-hero {cls}"><div class="w2-hi"><picture>{srcset(f)}<img src="{ST}/img/{f}" alt="" decoding="async" fetchpriority="high" data-par></picture></div>'
            f'<div class="w2-hc w2-rv"><p class="w2-eb">{eyebrow}</p><{tag} class="w2-ht">{E(title)}</{tag}>'
            + (f'<p class="w2-hl">{E(line)}</p>' if line else "") + (btn or "") + '</div>'
            + (credit_html(img_key) if credit else "") + '</section>')

def btn(href, label, cls=""):
    return f'<a class="w2-btn {cls}" href="{E(href)}">{E(label)}<svg viewBox="0 0 20 10" aria-hidden="true"><path d="M0 5h18M14 1l4 4-4 4" fill="none" stroke="currentColor"/></svg></a>'

def _x_btn(it, headline=None):
    """Post on X with hashtags in the composer text only (x_share.py)."""
    import x_share
    return x_share.button_html(it, headline=headline, cls="w2-btn-s")

def items(state):
    m = [x for x in (state.get("main") or []) if not x.get("hidden")]
    try:
        import story_writer as SW
        m = [x for x in m if SW.allow(x.get("cluster_id") or x.get("id"))]
    except Exception:
        pass
    m.sort(key=lambda x: str(x.get("updated") or ""), reverse=True)
    m.sort(key=lambda x: -(x.get("rank") or 0))   # stable: rank first, newest change first within a rank
    return m

# ---------------------------------------------------------------- /wire
def render_list(state, path="/wire", noindex=False):
    m = items(state); used = Used(); used.take(["list_hero"])
    gen = et(state.get("generated"))
    top = m[0] if m else None
    body = hero("list_hero", "THE WIRE", "What matters now", f"{len(m)} ranked stories · updated {gen}",
                btn("#w2_top", "Top story"), cls="w2-hero-list")
    if top:
        k = used.take(img_keys(top)) or used.take(["night"]) or "night"
        p = brief_parts(top.get("brief"))
        body += (f'<section class="w2-hero w2-hero-top" id="w2_top"><div class="w2-hi"><picture>{srcset(IMG[k][0])}<img src="{ST}/img/{IMG[k][0]}" alt="" loading="lazy" decoding="async" data-par></picture></div>'
                 f'<div class="w2-hc w2-rv"><p class="w2-eb">TOP STORY · {E((top.get("category") or "").upper())}</p>{rank_block(top.get("rank"), True)}'
                 f'<h2 class="w2-ht w2-ht-s">{E(headline(top.get("title")))}</h2><p class="w2-hl">{E(dek_for(top, headline(top.get("title"))))}</p>'
                 f'{btn("/wire/" + top["cluster_id"], "Read story")}</div>{credit_html(k)}</section>')
    rest = m[1:]; bands = []
    for it in rest:                       # up to 2 full-bleed feature bands, each with a fresh, relevant image
        if len(bands) == 2: break
        ks = [k for k in img_keys(it) if k not in used.s]
        if ks and (it.get("rank") or 0) >= 6: used.take(ks[:1]); bands.append((it, ks[0]))
    band_ids = {b[0]["cluster_id"] for b in bands}
    rest = [x for x in rest if x["cluster_id"] not in band_ids]
    def band(it, k):
        h = headline(it.get("title"))
        return (f'<section class="w2-hero w2-hero-band w2-feat"><div class="w2-hi"><picture>{srcset(IMG[k][0])}<img src="{ST}/img/{IMG[k][0]}" alt="" loading="lazy" decoding="async" data-par></picture></div>'
                f'<div class="w2-hc w2-rv"><p class="w2-eb">{E((it.get("category") or "").upper())}</p>{rank_block(it.get("rank"), True)}<h2 class="w2-ht w2-ht-s">{E(h)}</h2>'
                f'<p class="w2-hl">{E(dek_for(it, h))}</p>{btn("/wire/" + it["cluster_id"], "Read story")}</div>{credit_html(k)}</section>')
    rows = []
    for i, it in enumerate(rest[:40]):
        p = brief_parts(it.get("brief")); cid = it["cluster_id"]
        meta = " · ".join(x for x in [it.get("location") or "", f'{it.get("n_families") or 1} independent source' + ("s" if (it.get("n_families") or 1) != 1 else ""), ago(it.get("updated"))] if x)
        links = "".join(f'<li><a href="{E(l.get("url"))}" rel="noopener nofollow" target="_blank">{E(l.get("source") or "Source")}</a></li>' for l in (it.get("links") or [])[:4] if str(l.get("url", "")).startswith("http"))
        rows.append(
            f'<article class="w2-row w2-rv{" w2-more" if i >= 9 else ""}"{" hidden" if i >= 9 else ""}>{rank_block(it.get("rank"))}'
            f'<div class="w2-rb"><p class="w2-eb">{E((it.get("category") or "").upper())}</p><h3 class="w2-rh"><a href="/wire/{E(cid)}">{E(headline(it.get("title")))}</a></h3>'
            f'<p class="w2-meta">{E(meta)}</p><details class="w2-det"><summary>DETAILS</summary><p>{E(first_sentence(p.get("what") or "", 220))}</p>'
            + (f'<ul class="w2-src">{links}</ul>' if links else "") + f'{btn("/wire/" + cid, "Open story", "w2-btn-s")}</details></div></article>')
    more = f'<div class="w2-morew"><button type="button" class="w2-btn" id="w2_more">More stories</button></div>' if len(m) > 7 else ""
    head = '<header class="w2-sh w2-rv"><p class="w2-eb">RANKED NOW</p><h2 class="w2-h2">The board</h2></header>'
    body += f'<section class="w2-sec"><div class="w2-wrap">{head}<div class="w2-rows">{"".join(rows[:3])}</div></div></section>'
    if bands: body += band(*bands[0])
    body += f'<section class="w2-sec"><div class="w2-wrap"><div class="w2-rows">{"".join(rows[3:6])}</div></div></section>'
    if len(bands) > 1: body += band(*bands[1])
    body += f'<section class="w2-sec"><div class="w2-wrap"><div class="w2-rows">{"".join(rows[6:])}</div>{more}</div></section>'
    wl = state.get("watchlist_count") or len(state.get("watchlist") or [])
    body += hero("night", "WATCHLIST", f"{wl} signals waiting", "Single-source reports wait here until a second, independent source confirms them.",
                 btn("/live#threat", "Open watchlist"), cls="w2-hero-band", h1=False)
    return shell("The Wire: ranked threat alerts | BLACKOUT.NETWORK", "Every ranked alert, sorted by rank, with the latest changes on top.", body, path, noindex=noindex)

# ---------------------------------------------------------------- /wire/<id>
def render_story(state, cid):
    try:  # BN_STORY_V3: full narrative story pages (on by default; BN_STORY_V3=0 turns it off)
        import story_v3 as V3
        if V3.on():
            html = V3.render(state, cid)
            if html: return html
    except Exception:
        import traceback; traceback.print_exc()
    m = items(state); it = next((x for x in m + (state.get("watchlist") or []) if x.get("cluster_id") == cid), None)
    if not it: return None
    used = Used(); k = used.take(img_keys(it)) or used.take(["night"])
    p = brief_parts(it.get("brief")); r = int(it.get("rank") or 0); full = it.get("title") or ""
    h = headline(full); cat = (it.get("category") or "").upper()
    meta = f'Seen {et(it.get("first_seen"))} · Updated {et(it.get("updated"))}'
    body = (f'<section class="w2-hero w2-hero-story"><div class="w2-hi"><picture>{srcset(IMG[k][0])}<img src="{ST}/img/{IMG[k][0]}" alt="" decoding="async" fetchpriority="high" data-par></picture></div>'
            f'<div class="w2-hc w2-rv"><p class="w2-eb"><a href="/wire">THE WIRE</a> / {E(cat)}</p>{rank_block(r, True)}<h1 class="w2-ht w2-ht-s">{E(h)}</h1>'
            + (f'<p class="w2-hl">{E(first_sentence(full, 140))}</p>' if h != full else "") + f'<p class="w2-meta">{E(meta)}</p></div>'
            f'{credit_html(k)}</section>')
    nf = it.get("n_families") or 1
    bottom = (f"A {RANK_NAMES.get(r, '').lower()} {(it.get('category') or 'story').lower()} story, reported by {nf} independent source{'s' if nf != 1 else ''}"
              + (", none of them official yet." if r and nf < 2 else "."))
    body += (f'<section class="w2-sec"><div class="w2-wrap w2-narrow w2-rv"><p class="w2-eb">BOTTOM LINE</p><p class="w2-lead">{E(bottom)}</p></div></section>')
    when = (p.get("when") or "").split(" / ")[-1].rstrip(".")
    where = "" if re.search(r"not specified", p.get("where") or "", re.I) else (p.get("where") or it.get("location") or "")
    nm = lambda x: re.sub(r"[^a-z0-9]+", "", (x or "").lower())
    what = "" if nm(p.get("what"))[:60] in nm(full) or nm(full)[:60] in nm(p.get("what")) else p.get("what")
    facts = [(lab, v) for lab, v in (("What", what), ("Where", where), ("When", when)) if v]
    if facts:
        body += ('<section class="w2-sec w2-sec-t"><div class="w2-wrap w2-rv"><p class="w2-eb">KEY FACTS</p><div class="w2-facts">'
                 + "".join(f'<div class="w2-fact"><p class="w2-fl">{E(l.upper())}</p><p class="w2-fv">{E(first_sentence(v, 200))}</p></div>' for l, v in facts)
                 + '</div></div></section>')
    body += (f'<section class="w2-sec w2-sec-t"><div class="w2-wrap w2-rv"><p class="w2-eb">CONFIDENCE</p><h2 class="w2-h2">{nf} independent source{"s" if nf != 1 else ""}</h2>'
             f'{sources_graphic(nf, it.get("families"))}<p class="w2-meta">{E(it.get("n_items") or 0)} reports logged. Rank {r} of 10, {E(RANK_NAMES.get(r, ""))}.</p></div></section>')
    links = "".join(f'<li><a href="{E(l.get("url"))}" rel="noopener nofollow" target="_blank">{E(l.get("source") or "Source")}</a></li>' for l in (it.get("links") or [])[:12] if str(l.get("url", "")).startswith("http"))
    body += ('<section class="w2-sec w2-sec-t"><div class="w2-wrap w2-narrow">'
             + (f'<details class="w2-acc w2-rv"><summary>SOURCES<i></i></summary><ul class="w2-src">{links}</ul></details>' if links else "")
             + (f'<details class="w2-acc w2-rv"><summary>FULL REPORT<i></i></summary><p>{E(p.get("what") or "")}</p>' + (f'<p class="w2-meta">{E(p.get("confidence"))}</p>' if p.get("confidence") else "") + '</details>')
             + '<details class="w2-acc w2-rv"><summary>HOW WE RANK<i></i></summary><p>Ranks run 0 to 10. They are set by published scoring rules and confirmed by counting independent sources.</p><p><a href="/scoring">How we score →</a></p></details>'
             + f'<div class="w2-share w2-rv">{_x_btn(it, h)}'
               '<button type="button" class="w2-btn w2-btn-s" data-copy>Copy link</button></div></div></section>')
    nxt = [x for x in m if x.get("cluster_id") != cid][:3]
    if nxt:
        body += ('<section class="w2-sec w2-sec-t"><div class="w2-wrap"><p class="w2-eb w2-rv">MORE ON THE WIRE</p><div class="w2-rows">'
                 + "".join(f'<article class="w2-row w2-rv">{rank_block(x.get("rank"))}<div class="w2-rb"><p class="w2-eb">{E((x.get("category") or "").upper())}</p>'
                           f'<h3 class="w2-rh"><a href="/wire/{E(x["cluster_id"])}">{E(headline(x.get("title")))}</a></h3><p class="w2-meta">{E(ago(x.get("updated")))}</p></div></article>' for x in nxt)
                 + f'</div><div class="w2-morew">{btn("/wire", "All stories")}</div></div></section>')
    return shell(f"{h} | BLACKOUT.NETWORK", first_sentence(full, 150), body, f"/wire/{cid}", rank=int(it.get("rank") or 0))

_IMGC = {}
def handle_static(path):
    """/wire2/static/<file>.css|js and /wire2/static/img/<name>.webp. Images live in the repo as base64 text (img/<name>.webp.b64,
    the GitHub tooling here commits text only); decoded once and kept in memory (~1 MB for all 14)."""
    import base64
    p = path[len(ST) + 1:]
    if not re.fullmatch(r"[a-z0-9_]+\.(css|js)|img/[a-z0-9_]+\.webp|vid/[a-z0-9_]+\.mp4", p): return None
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wire_v2_static", p)
    ext = p.rsplit(".", 1)[1]
    ct = {"css": "text/css", "js": "application/javascript", "webp": "image/webp", "mp4": "video/mp4"}[ext]
    if ext not in ("webp", "mp4"):
        return (200, open(fp, "rb").read(), ct) if os.path.isfile(fp) else None
    b = _IMGC.get(p)
    if b is None:
        if os.path.isfile(fp): b = open(fp, "rb").read()
        elif os.path.isfile(fp + ".b64"): b = base64.b64decode(open(fp + ".b64", "rb").read())
        else: return None
        _IMGC[p] = b
    return 200, b, ct

_C = {}
_NEG = {}
_INFL = {}
_RP = None
_BUDGET = 1.5   # a cold page that needs the live board (api_state can take tens of seconds when its cache is stale) answers with an OG-complete stub after this


def _pool():
    global _RP
    if _RP is None:
        from concurrent.futures import ThreadPoolExecutor
        _RP = ThreadPoolExecutor(max_workers=4, thread_name_prefix="wire-page")
    return _RP


def _build(key, list_path, noindex):
    try:
        srv = __import__("theme")._srv()
        st = srv.api_state()
        body = render_list(st, path=list_path, noindex=noindex) if key in ("/wire", "/wire-classic") else render_story(st, key)
        if body:
            if len(_C) > 300: _C.clear()
            _C[key] = (time.time(), body)
        else:
            _NEG[key] = time.time()
        return body
    finally:
        _INFL.pop(key, None)


def _light_story(cid):
    """Instant page for crawlers and first-time visitors while the full page builds: complete og:/twitter: tags from the DB (title, summary, card URL)."""
    try:
        import story, og
        r, _al = story.load(cid)
        if not r: return None
        full = r.get("title") or ""
        h = headline(full) or full
        rank = int(r.get("rank") or 0)
        brief = r.get("brief") or ""
        desc = first_sentence(brief or full, 160)
        meta = og.tags(title=f"{h} | BLACKOUT.NETWORK", desc=desc, url=f"{og.SITE}/wire/{cid}", story_id=cid, rank=rank, og_type="article")
        fall = f"/wire/{cid}?full=1"
        return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                f"<title>{E(h)} | BLACKOUT.NETWORK</title><link rel=\"canonical\" href=\"{E(og.SITE)}/wire/{E(cid)}\">{meta}"
                f"<meta http-equiv=\"refresh\" content=\"3;url={E(fall)}\"></head>"
                f"<body style=\"background:#05060a;color:#ECEEF5;font:16px/1.5 Inter,system-ui,sans-serif;padding:48px 24px\">"
                f"<h1 style=\"font-size:22px\">{E(h)}</h1><p style=\"color:#9aa0aa\">Loading the full story…</p>"
                f"<p><a href=\"{E(fall)}\" style=\"color:#ECEEF5\">Open the full story</a></p>"
                f"<script>setTimeout(function(){{location.replace({json.dumps(fall)});}},3000);</script></body></html>")
    except Exception:
        return None


def _ua(headers):
    if not headers: return ""
    return headers.get("user-agent") or headers.get("User-Agent") or ""


def _qs_flag(qs, name):
    v = (qs or {}).get(name)
    if isinstance(v, (list, tuple)):
        v = v[0] if v else ""
    return str(v or "").strip().lower() in ("1", "true", "yes")


def handle(path, qs=None, headers=None):
    """(code, body, ctype) for /wire, /wire-classic, /wire/<id> when ON, else None (caller falls back to the DB story page).
    A cached board page is served at once (refreshed in the background after 60 s). Humans never wait on api_state and
    never see the 'Loading the full story…' stub — handle returns None and story.py renders title, brief, sources and
    the share button from the DB. The OG stub is only for crawler UAs (Twitterbot, facebookexternalhit, …) and its
    auto-refresh hard-falls back to /wire/<id>?full=1 (the DB page). There is no second, 20-second wait."""
    if not ON: return None
    list_path, noindex = "/wire", False
    if path in ("/wire-classic", "/wire-classic/"):
        key, list_path, noindex = "/wire-classic", "/wire-classic", True
    elif path in ("/wire", "/wire/"):
        key = "/wire"
    else:
        m = re.match(r"^/wire/([0-9a-f]{16})/?$", path)
        if not m or (qs or {}).get("since") or _qs_flag(qs, "full"): return None
        key = m.group(1)
    now = time.time()
    hit = _C.get(key)
    if hit:
        if now - hit[0] >= 60 and key not in _INFL:
            _INFL[key] = _pool().submit(_build, key, list_path, noindex)
        if now - hit[0] < 1800:   # serve stale up to 30 min while it refreshes
            return 200, hit[1], "text/html"
    story_page = key not in ("/wire", "/wire-classic")
    crawler = False
    if story_page:
        try:
            import og
            crawler = og.is_crawler(_ua(headers))
        except Exception:
            crawler = False
        if not crawler:
            return None   # human: do not start api_state (it can lock the DB); caller renders from the DB
    if _NEG.get(key) and now - _NEG[key] < 60: return None
    fut = _INFL.get(key)
    if fut is None:
        fut = _INFL[key] = _pool().submit(_build, key, list_path, noindex)
    if story_page and crawler:
        # Nov 25 2026 (X cards): a crawler (Twitterbot) gives up after a few seconds. Never make it wait on the live
        # board build (1.5 s budget + a 1-5 s DB render): answer at once with the OG-complete stub from the DB while the
        # full page builds in the background for the next hit.
        light = _light_story(key)
        if light: return 200, light, "text/html"
    try:
        body = fut.result(timeout=_BUDGET)
    except Exception:
        if story_page and crawler:
            light = _light_story(key)
            if light: return 200, light, "text/html"
        return None
    if not body: return None   # story no longer on the board: old story page (DB history) handles it
    return 200, body, "text/html"
