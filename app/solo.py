"""Reworked standalone pages (Nov 24 2026, Matt pt1846u): pages pulled in the menu rebuild (deactivated.py) come back one batch at a
time as their own dark SpaceX-theme pages instead of /live#<tab> panels. Each page = the shared w2 shell (text wordmark, menu, footer)
+ a plain hero + the existing content (static guide HTML, or the tab add-on's own JS/CSS run inside a single <main>).
Pages stay "unlisted" in deactivated.py (they serve, but no menu/footer/sitemap link) until Matt approves them for the menu.
Nothing here touches the scanner, databases or other modules; the add-on JS/CSS/APIs are reused as they are (emoji stripped on the way out).
Kill switch: BN_SOLO=0 sends these paths back to the previous behaviour (302 to the /live tab)."""
import os, re, html

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "solo_static")
GUIDES = os.path.join(BASE, "static", "guides")
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
on = lambda: os.environ.get("BN_SOLO", "1") != "0"

# Emoji / pictographs (and their joiners, variation selectors and flag letters). Plain marks like a check or an arrow are kept.
_EMO = re.compile("(?:[\U0001F000-\U0001FAFF]|[\u2600-\u2604\u2607-\u260F\u2613-\u26FF]|[\u2700-\u2712\u2714\u2716-\u27BF]|[\u2B00-\u2BFF]|[\u23E9-\u23FA\u23CF\u2328\u24C2\u3030\u303D\u3297\u3299]|[\uFE0E\uFE0F\u200D\u20E3])[ ]?")
_KEYCAP = re.compile("[0-9#*]\uFE0F?\u20E3[ ]?")
def demoji(s): return _EMO.sub("", _KEYCAP.sub("", s))

# Yellow brand accents are retired (amber = degraded only): map the old guide yellows to the neutral light grey.
_YEL = re.compile(r"#(?:ffd666|ffe58f|fadb14|fde047|facc15|fbbf24)\b", re.I)
def deyellow(s): return _YEL.sub("#d6d8dc", s)

# key -> page. kind "guide" = static/guides/<file> rendered server-side; kind "tab" = the old dashboard tab add-on run in one <main>.
PAGES = {
    "games":     dict(paths=("/games",), kind="tab", tab="games", eb="Play", h1="Games",
                      lede="Original 8-bit arcade, puzzle and board games. Free, no sign-up, nothing to install.",
                      title="Games: original 8-bit arcade, puzzle and board games | BLACKOUT.NETWORK",
                      desc="Original 8-bit style arcade, puzzle and board games you can play in your browser. Free, no sign-up, scores saved on your device.",
                      css="/api/games/app.css", js="games"),
    "preppers":  dict(paths=("/preppers",), kind="tab", tab="preppers", eb="Prepare", h1="Preppers",
                      lede="Rated suppliers, free official guidance, a supply planner and kits for every scenario.",
                      title="Preppers: rated suppliers, supply planner and scenario kits | BLACKOUT.NETWORK",
                      desc="A rated directory of preparedness suppliers, free official guidance, a household supply planner and kits for every scenario. No affiliate links.",
                      css="/api/preppers/app.css", js="preppers",
                      main='<section class="pn"><div id="pp_app"><div class="meta">Loading</div></div></section>'),
    "bushcraft": dict(paths=("/bushcraft",), kind="guide", tab="bush", file="bushcraft.html", eb="Prepare", h1="Bushcraft",
                      lede="A grid-down field guide: water, fire, shelter, food, navigation and signaling. Print it while the power is on.",
                      title="Bushcraft: grid-down field guide | BLACKOUT.NETWORK",
                      desc="BLACKOUT.NETWORK's grid-down bushcraft guide: water, fire, shelter, food, navigation and signaling, written to be printed and used without internet."),
    "medical":   dict(paths=("/medical", "/first-aid"), kind="guide", tab="med", file="medical.html", eb="Prepare", h1="First aid",
                      lede="What to do until help arrives: scene safety, bleeding, burns, CPR, choking, heat illness and medicines.",
                      title="First aid: what to do until help arrives | BLACKOUT.NETWORK",
                      desc="Plain-language first aid for emergencies and outages: bleeding control, burns, fractures, CPR, choking, allergic reactions, heat illness and medication storage."),
    # batch 2 (data tabs)
    "noise":     dict(paths=("/noise",), kind="tab", tab="noise", eb="Signals", h1="Background noise",
                      lede="Every lower-priority alert the scanner logs, ranked 0 to 6 and newest first: what is simmering before it becomes news.",
                      title="Background noise: low-rank alerts | BLACKOUT.NETWORK",
                      desc="Every lower-priority alert BLACKOUT.NETWORK's scanner logs, ranked 0 to 6 and newest first, so you can see what is simmering before it becomes news.",
                      css="/api/noise/app.css", js="noise"),
    "politics":  dict(paths=("/politics",), kind="tab", tab="politics", eb="Politics", h1="Politics",
                      lede="Political developments flagged by the scanner, next to public prediction-market prices: what might shift and how fast.",
                      title="Politics: developments and markets | BLACKOUT.NETWORK",
                      desc="Political developments flagged by BLACKOUT.NETWORK's scanner, alongside public prediction-market prices, so you can see what might shift and how fast.",
                      css="/api/politics/app.css", js="politics"),
    "government": dict(paths=("/government",), kind="tab", tab="gov", eb="Government", h1="Government",
                      lede="Government organisations we track: who runs what, how they are organised and the latest from each.",
                      title="Government: organisations and leadership | BLACKOUT.NETWORK",
                      desc="Government organisations tracked on BLACKOUT.NETWORK: an org chart, leadership profiles and the latest updates.",
                      css="/api/government/app.css", js="government"),
    "figures":   dict(paths=("/figures", "/elon"), kind="tab", tab="figures", eb="People", h1="Key figures",
                      lede="A neutral reference to the people named in the stories we follow: current role, why they are in the news and the latest headlines.",
                      title="Key figures: people in the news | BLACKOUT.NETWORK",
                      desc="A neutral reference to the people named in the stories BLACKOUT.NETWORK follows: their current role, why they are in the news and the latest headlines.",
                      css="/api/figures/app.css", js="figures"),
    # batch 3
    "ai":        dict(paths=("/ai", "/aithreats", "/ai-threats"), kind="tab", tab="ai", eb="Monitor", h1="AI threats",
                      lede="AI-assisted hacking, rogue bots and agents, AI-enabled cyber attacks, deepfake fraud and model misuse, ranked 0 to 10.",
                      title="AI Threats: AI-driven attacks and fraud | BLACKOUT.NETWORK",
                      desc="BLACKOUT.NETWORK tracks AI threats: AI-assisted hacking, rogue bots and agents, AI-enabled cyber attacks, deepfake fraud and model misuse, ranked 0 to 10.",
                      css="/api/ai/app.css", js="ai"),
    "gunlaws":   dict(paths=("/gunlaws",), kind="tab", tab="gunlaws", eb="Law", h1="Gun laws",
                      lede="Second Amendment cases in U.S. courts, gun bills in Congress and state ballot measures, with parties, odds and plain-English forecasts.",
                      title="Gun Laws: court cases, bills and forecasts | BLACKOUT.NETWORK",
                      desc="Second Amendment cases in U.S. courts, gun bills in Congress and state ballot measures on BLACKOUT.NETWORK, with parties, odds and plain-English forecasts.",
                      css="/api/gunlaws/app.css", js="gunlaws"),
    "spacex":    dict(paths=("/spacex",), kind="tab", tab="spacex", eb="Space", h1="SpaceX",
                      lede="Next-launch countdown, the full launch schedule, Starship and Starlink updates, recent news and related prediction markets.",
                      title="SpaceX: launches, Starship and Starlink | BLACKOUT.NETWORK",
                      desc="SpaceX on BLACKOUT.NETWORK: next-launch countdown, the full launch schedule, Starship and Starlink updates, recent news and related prediction markets.",
                      css="/api/spacex/app.css", js="spacex"),
}
PATHS = {p: k for k, v in PAGES.items() for p in v["paths"]}

def _read(p):
    try:
        with open(p, encoding="utf-8") as f: return f.read()
    except OSError: return ""

def _ver(*files):
    try: return str(int(max(os.path.getmtime(f) for f in files if os.path.exists(f))))[-8:]
    except ValueError: return "0"

def _dash_main(tab):
    """The tab's <main id="tab-..."> markup from dashboard.html (shown, emoji stripped), or ""."""
    s = _read(os.path.join(BASE, "dashboard.html"))
    m = re.search(r'<main id="tab-' + re.escape(tab) + r'"[^>]*>(.*?)</main>', s, re.S)
    return demoji(m.group(1)) if m else ""

def _guide(pg):
    body = deyellow(demoji(_read(os.path.join(GUIDES, pg["file"]))))
    css = deyellow(_read(os.path.join(GUIDES, "guide.css")))
    if not body: body = '<p class="meta">This guide is not available right now.</p>'
    return f'<style>{css}</style><div id="gd_{pg["tab"]}">{body}</div>'

def page_html(key):
    pg = PAGES[key]
    try:
        import wire_v2; menu = wire_v2.menu_html(); w2 = wire_v2.ST
    except Exception:
        menu = ""; w2 = "/wire2/static"
    canon = "https://blackout.network" + pg["paths"][0]
    try:
        import og; ogmeta = og.tags(title=pg["title"], desc=pg["desc"], url=canon, key=key, og_type="website")
    except Exception: ogmeta = ""
    tab = pg["tab"]
    if pg["kind"] == "guide":
        inner = _guide(pg); assets_css = ""; assets_js = ""
    else:
        inner = pg.get("main") or _dash_main(tab)
        assets_css = f'<link rel="stylesheet" href="{pg["css"]}">'
        assets_js = (f'<script src="/api/solo/shim.js?v={_ver(os.path.join(STATIC, "shim.js"))}"></script>'
                     f'<script src="/api/solo/js/{pg["js"]}.js?v={_ver(_addon_js_path(pg["js"]))}"></script>')
    sv = _ver(os.path.join(STATIC, "solo.css"), os.path.join(STATIC, "solo.js"))
    # A tab whose add-on builds its own <main> (no markup in dashboard.html) gets an empty slot; solo.js moves the built <main> into it.
    main = (f'<main id="tab-{E(tab)}" data-addon="{E(tab)}" class="solo-main">{inner}</main>' if inner
            else f'<div id="solo_slot" class="solo-main solo-slot"><p class="meta">Loading</p></div>')
    return f'''<!doctype html><html lang="en" data-bn-w2><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{E(pg["title"])}</title><meta name="description" content="{E(pg["desc"])}"><link rel="canonical" href="{canon}">
{ogmeta}<meta name="theme-color" content="#000">
<link rel="stylesheet" href="{w2}/wire2.css?v=10">{assets_css}<link rel="stylesheet" href="/api/solo/solo.css?v={sv}"></head>
<body class="w2 solo solo-{E(key)}" data-solo="{E(tab)}"><header class="w2-bar" id="w2_bar"><a class="w2-wm" href="/?intro=1" aria-label="BLACKOUT.NETWORK intro">blackout.network</a>
<button type="button" class="w2-mbtn" id="w2_open" aria-label="Open menu" aria-controls="w2_menu" aria-expanded="false"><span class="bn-hx" aria-hidden="true"><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span></span></button></header>
{menu}
<section class="solo-hero" aria-label="{E(pg["h1"])}"><div class="solo-hc"><p class="w2-eb">{E(pg["eb"])}</p><h1 class="w2-ht">{E(pg["h1"])}</h1>
<p class="w2-hl">{E(pg["lede"])}</p></div></section>
<nav class="tabs" hidden aria-hidden="true"></nav>
{main}
<footer class="w2-foot"><p class="w2-tag">Global threat monitoring</p><p class="w2-legal">Independent early-warning signals. Not an official alert service. <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a> · <a href="/credits">Image credits</a></p></footer>
<script src="{w2}/wire2.js?v=3" defer></script>{assets_js}<script src="/api/solo/solo.js?v={sv}"></script></body></html>'''

ADDON_JS = {"games": "games_static", "preppers": "preppers_static", "noise": "bnoise_static", "politics": "politics_static",
            "government": "government_static", "figures": "figures_static",
            "ai": "tabfeeds_static", "gunlaws": "gunlaws_static", "spacex": "spacex_static"}
ADDON_JS = {k: os.path.join(BASE, d, "app.js") for k, d in ADDON_JS.items()}
def _addon_js_path(name): return ADDON_JS.get(name, "")

def handle_get(path, qs):
    p = path.rstrip("/") or "/"
    if p in PATHS:
        if not on(): return 404, {"error": "not found"}   # server.not_found_page then 302s to the /live tab as before
        return 200, page_html(PATHS[p]), "text/html"
    if path.startswith("/api/solo/"):
        n = path[len("/api/solo/"):]
        if n in ("solo.css", "solo.js", "shim.js"):
            b = _read(os.path.join(STATIC, n))
            return (200, b.encode("utf-8"), "text/css" if n.endswith("css") else "application/javascript") if b else (404, {"error": "not found"})
        m = re.fullmatch(r"js/([a-z]+)\.js", n)
        if m and m.group(1) in ADDON_JS:
            b = _read(ADDON_JS[m.group(1)])
            if b:
                b = demoji(b)
                if m.group(1) == "politics":
                    # Don't depend on dashboard.html's dataRange or a $() that missed #pol_range (pt1847u).
                    b = b.replace(
                        'try{$("pol_range").textContent=(typeof dataRange=="function"?dataRange(AL):"")+` · alerts updated ${etF(D.generated)}`}catch(_){}',
                        'try{var el=document.getElementById("pol_range");if(el)el.textContent=(typeof dataRange=="function"?dataRange(AL||[]):"Data range: no items loaded")+" · alerts updated "+etF(D.generated)}catch(_){}')
                return 200, b.encode("utf-8"), "application/javascript"
    return 404, {"error": "not found"}
