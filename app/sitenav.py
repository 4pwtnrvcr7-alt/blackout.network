"""Shared site header, main nav and per-page SEO metadata for BLACKOUT.NETWORK (t301/t302).

ONE source of truth for:
  * the tab bar (groups, order, labels, #hash routes) used by the dashboard AND every standalone page,
  * the header pills, including "Follow us on YouTube / X",
  * the title + meta description of every page and every dashboard tab.
Standalone pages (/scoring, /sources, /newsletter, /privacy, /tos, /report-status) render header_html()/head_html()
server-side (works without JavaScript). The dashboard loads /sitenav.js, which is static/sitenav.js with this
module's data embedded, so the dashboard's tab order, the per-tab title/description and the tab bar on every other
page all come from NAV/TABS below. Add a new dashboard tab here once and it shows up everywhere.
Served at /sitenav.js and /sitenav.css (routes in addons.py)."""
import os, sys, json, html

BASE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://blackout.network"
BRAND = "BLACKOUT.NETWORK"
TAGLINE = "Know first. Be ready."
YT_URL = "https://www.youtube.com/@blkoutntw"
X_URL = "https://x.com/BlkoutNtw"
HANDLE = "@BlkoutNtw"

# (tab key, #hash, label, title, meta description). Order and grouping = the dashboard tab bar.
# key "@scoring" is the link to the /scoring page (not a dashboard tab). hidden=True tabs are parked (THREAD_ENABLED=false).
NAV = [
 ("Monitor", [
  ("threat", "wire", "📡 The Wire", "The Wire: live threat feed",
   "BLACKOUT.NETWORK's free early-warning feed: breaking outbreaks, quakes, cyber attacks, unrest and conflict, each ranked 0–10 and linked to its sources."),
  ("noise", "noise", "🔉 Background Noise", "Background Noise: low-rank alerts",
   "Every lower-priority alert BLACKOUT.NETWORK's scanner logs, ranked 0 to 6 and newest first, so you can see what is simmering before it becomes news."),
  ("thread", "thread", "🧵 The Thread", "The Thread: developing stories",
   "BLACKOUT.NETWORK's Thread links related alerts into developing stories, showing every update, its sources and how the threat level changed over time.", True),
  ("bcast", "broadcasts", "📻 Live Broadcasts", "Live Broadcasts: wire, TV and radio",
   "Live wire, local TV and radio transcripts on BLACKOUT.NETWORK, searched for threat keywords and color-coded by category as they come in, around the clock."),
  ("streams", "streams", "📺 Live Streams", "Live Streams: news channels live now",
   "Watch news channels streaming live right now on BLACKOUT.NETWORK, each one watched and transcribed so you can catch breaking events as they air."),
  ("radio", "radio", "📻 Radio", "Radio: number stations and live HF",
   "Listen to number stations, military HF and live radio on BLACKOUT.NETWORK, playable right in your browser, with a rolling transcript and a location filter."),
  ("net", "network", "🌐 Network Status", "Network Status: internet and cloud",
   "Live status of the internet, cloud providers, major apps and ISPs on BLACKOUT.NETWORK, with outage alerts and recent history so you know if it is just you."),
  ("grid", "grid", "⚡ Energy Grid", "Energy Grid: power grid status",
   "BLACKOUT.NETWORK maps the U.S. power grid by operator, colored by current status, with local outage counts, grid alerts and weather-driven stress checks."),
  ("ai", "ai", "🤖 AI Threats", "AI Threats: AI-driven attacks and fraud",
   "BLACKOUT.NETWORK tracks AI threats: AI-assisted hacking, rogue bots and agents, AI-enabled cyber attacks, deepfake fraud and model misuse, ranked 0–10."),
  ("solar_seismic", "solar", "☀ Solar & Seismic", "Solar & Seismic: space weather and quakes",
   "Space weather and earthquakes on BLACKOUT.NETWORK: solar flares, geomagnetic storms, the Kp index and live global quakes, plus a solar–quake correlation lab."),
  ("heatmap", "heatmap", "🔥 Heat Map", "Heat Map: where the alerts are",
   "BLACKOUT.NETWORK's regional heat map shows where threat alerts cluster, from countries down to states, provinces and cities, updated with every scan."),
  ("@crime", "/crime", "🚨 Crime", None, None),   # /crime page (crime.py, t392): rates by ZIP/city/county/state/country + near-real-time city heat maps
  ("weather", "weather", "🌦 Weather", "Weather: alerts and forecast",
   "Current conditions, official severe-weather alerts and the forecast for any place you choose, on BLACKOUT.NETWORK. Free, with no account or sign-up needed."),
  ("trends", "trends", "📈 Trends", "Trends: alert volume over time",
   "See how BLACKOUT.NETWORK's alert volume, severity mix and source health have moved over hours, days and weeks, with charts you can read on any screen."),
  ("politics", "politics", "🏛 Politics", "Politics: developments and markets",
   "Political developments flagged by BLACKOUT.NETWORK's scanner, alongside public prediction-market prices, so you can see what might shift and how fast."),
  ("gunlaws", "gunlaws", "⚖ Gun Laws", "Gun Laws: court cases, bills and forecasts",
   "Second Amendment cases in U.S. courts, gun bills in Congress and state ballot measures on BLACKOUT.NETWORK, with parties, odds and plain-English forecasts."),
  ("midterms", "midterms", "🗳 Midterms 2026", "Midterms 2026: races, polls and results",
   "The 2026 U.S. midterms on BLACKOUT.NETWORK: every Senate, House and governor race, with cited ratings, polls, market odds and official live results."),
  ("finance", "finance", "💹 Finance", "Finance: global markets",
   "Global markets on BLACKOUT.NETWORK: indices, ETFs, stocks, bonds, options and volatility, forex and crypto, in one dark, phone-friendly dashboard tab."),
  ("jets", "jets", "✈ Private jets", "Private jets: business jets airborne now",
   "Private and business jets airborne right now anywhere in the world, tracked on BLACKOUT.NETWORK from public transponder data and refreshed every few minutes."),
  ("spacex", "spacex", "🚀 SpaceX", "SpaceX: launches, Starship and Starlink",
   "SpaceX on BLACKOUT.NETWORK: next-launch countdown, the full launch schedule, Starship and Starlink updates, recent news and related prediction markets."),
  ("intel", "intel", "🗂 Intel Streams", "Intel Streams: research, leaks, patents",
   "BLACKOUT.NETWORK's Intel Streams: new research papers, leak releases, patents, mergers and market shocks, each linked to its source, with an RSS feed."),
 ]),
 ("Community", [
  ("ranked", "ranked", "🗳 Ranked by Users", "Ranked by Users: the crowd's threat level",
   "Vote on how serious each alert is and compare the crowd's 0–10 threat level with the scanner's own ranking, live on BLACKOUT.NETWORK. No sign-up needed."),
  ("@social", "/social", "▶ Videos & posts", None, None),   # /social page (social.py, t303): YouTube @blkoutntw + X @BLKOUTNTW
  ("@stats", "/stats", "📊 Public stats", None, None),       # /stats page (stats.py, t385): open aggregate traffic + YouTube/X numbers
  ("newsletter", "newsletter", "✉ Newsletter", "Newsletter: the threat brief by email",
   "Get BLACKOUT.NETWORK's highest-severity, source-verified threats by email once or twice a day. Free, double opt-in, and you can unsubscribe in one click."),
 ]),
 ("Reference", [
  ("res", "resources", "📍 Local Resources", "Local Resources: emergency services near you",
   "Find nearby emergency services and essentials, like hospitals, pharmacies, police and fire stations, for any place you choose on BLACKOUT.NETWORK."),
  ("maps", "maps", "🗺 Maps", "Maps: printable offline PDF maps",
   "Download printable PDF maps from BLACKOUT.NETWORK while the internet still works. They keep working offline when the grid or the network goes down."),
  ("gov", "government", "🏛 Government", "Government: U.S. government health index",
   "How the U.S. government is doing, on BLACKOUT.NETWORK: a 0–100 health index by branch and agency from public data, plus who holds office, President to mayors."),
  ("bush", "bushcraft", "🏕 Bushcraft", "Bushcraft: grid-down survival guide",
   "BLACKOUT.NETWORK's grid-down bushcraft guide covers water, fire, shelter, food, navigation and signaling, written to be read and used without internet."),
  ("med", "medical", "⛑ Medical", "Medical: grid-down first aid",
   "BLACKOUT.NETWORK's grid-down first-aid guide: bleeding control, burns, fractures, CPR, choking, allergic reactions and heat illness. Not medical advice."),
  ("preppers", "preppers", "🎒 Preppers", "Preppers: suppliers, guidance and kits",
   "Rated prepper suppliers, free official preparedness guidance, a supply planner and ready-made kit lists for every threat type, on BLACKOUT.NETWORK."),
  ("figures", "figures", "👥 Key Figures", "Key Figures: people in the news",
   "A neutral reference to the people named in the stories BLACKOUT.NETWORK follows: their current role, why they are in the news and the latest headlines."),
  ("@scoring", "/scoring", "📐 How we score", None, None),
  ("sources", "sources", "📚 Sources", "Sources: every source, rated 0–10",
   "Every source BLACKOUT.NETWORK uses, with item counts, profiles and a transparent 0–10 confidence rating, plus a global directory you can search."),
 ]),
 ("Play", [
  ("games", "games", "👾 Games", "Games: 8-bit arcade games",
   "Original 8-bit style arcade, puzzle and board games you can play right in your browser on BLACKOUT.NETWORK, on desktop or phone. Free, no download."),
 ]),
 ("", [
  ("tips", "tips", "☕ Tips", "Tips: support the project",
   "BLACKOUT.NETWORK is free to use. Leave a tip to help cover the scanners, data feeds and servers that keep this early-warning threat monitor running 24/7."),
 ]),
]

# Standalone pages: path -> (active nav key, title, meta description, visible one-line description).
PAGES = {
 "home": ("threat", "BLACKOUT.NETWORK | Know first. Be ready.",
          "BLACKOUT.NETWORK is a free early-warning threat monitor: outbreaks, quakes, space weather, cyber attacks and conflict, ranked 0–10 and linked to sources.",
          "Free early-warning threat monitor: threats ranked 0–10, every one linked to its sources."),
 "scoring": ("@scoring", "How we score | BLACKOUT.NETWORK",
             "How BLACKOUT.NETWORK scores threats: the 0–100 severity score and the 0–10 rank, explained factor by factor with real worked examples. Research only.",
             "How the 0–100 severity score and the 0–10 rank are calculated, factor by factor, with real examples."),
 "sources": ("sources", "Sources | BLACKOUT.NETWORK",
             "Every source BLACKOUT.NETWORK uses, with item counts, profiles and a transparent 0–10 confidence rating. Search the directory or suggest a new source.",
             "Every source we use, with item counts, profiles and a 0–10 confidence rating. Suggest one for review."),
 "newsletter": ("newsletter", "Newsletter | BLACKOUT.NETWORK",
                "Sign up for BLACKOUT.NETWORK's free email brief: the highest-severity, source-verified threats once or twice a day. Double opt-in, one-click unsubscribe.",
                "The highest-severity, source-verified threats by email, once or twice a day. Free, double opt-in."),
 "privacy": ("", "Privacy Policy | BLACKOUT.NETWORK",
             "BLACKOUT.NETWORK's Privacy Policy: what the site collects, how the newsletter and YouTube data are used and stored, retention, deletion and how to reach us.",
             "What we collect, how we use and protect it, how long we keep it, and how to ask us to delete it."),
 "tos": ("", "Terms of Service | BLACKOUT.NETWORK",
         "BLACKOUT.NETWORK's Terms of Service: acceptable use, research-only data with no warranty, limitation of liability, Florida governing law and contact details.",
         "The rules for using BLACKOUT.NETWORK: acceptable use, no warranty, liability limits and Florida law."),
 "social": ("@social", "Videos & posts | BLACKOUT.NETWORK",
            "BLACKOUT.NETWORK videos and posts: world threat updates and explainers from YouTube @blkoutntw and X @BLKOUTNTW, each with a full sourced story page.",
            "Our video reports and posts from YouTube and X, each with a full, sourced write-up on this site."),
 "stats": ("@stats", "Public stats: site traffic, YouTube and X | BLACKOUT.NETWORK",
           "BLACKOUT.NETWORK's open stats: daily visitors and page views, the most-read pages and stories, where readers come from, plus YouTube @blkoutntw and X @BlkoutNtw growth.",
           "Open, aggregate numbers for the site, YouTube and X. Totals only, nothing personal."),
 "crime": ("@crime", "Crime map and statistics near you: ZIP, city, county, country | BLACKOUT.NETWORK",
           "Look up crime for any US ZIP code, city, county or state, or any country: official FBI rates per 100,000 with trends, near-real-time incident heat maps for 16 US cities, a US county map and a world homicide map.",
           "Official crime rates for any ZIP, city, county, state or country, plus near-real-time maps for 16 US cities."),
 "report-status": ("", "Check a problem report | BLACKOUT.NETWORK",
                   "Check the status of a problem you reported to BLACKOUT.NETWORK using your report ID: whether it was received, reviewed or fixed, with no account needed.",
                   "Look up a problem you reported with its report ID and see whether it was received, reviewed or fixed."),
}

def tabs():
    for g, items in NAV:
        for it in items: yield g, it

YT_SVG = ('<svg class="bn-ico" width="17" height="12" style="width:17px;height:12px;flex:none;display:block" viewBox="0 0 24 17" aria-hidden="true" focusable="false">'
          '<rect width="24" height="17" rx="4" fill="#FF0033"/><path d="M9.6 4.9v7.2l6.2-3.6z" fill="#fff"/></svg>')
X_SVG = ('<svg class="bn-ico" width="12" height="12" style="width:12px;height:12px;flex:none;display:block" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path fill="currentColor" '
         'd="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z"/></svg>')
# Inline styles so the pill looks right even where /sitenav.css hasn't loaded yet.
_PILL = ("display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:600;letter-spacing:.2px;line-height:1.25;border:1px solid var(--bd2,#2f3742);"
         "color:var(--tx,#e6e9ee);background:#14181d;border-radius:10px;padding:4px 9px;margin:4px 0 0 6px;vertical-align:middle;white-space:nowrap;text-decoration:none")

def social_html():
    def a(href, svg, net):
        return (f'<a class="bn-follow" href="{href}" target="_blank" rel="noopener me" title="Follow {BRAND} on {net} ({HANDLE})" style="{_PILL}">'
                f'{svg}<span>Follow us on {net} <b style="color:var(--ac,#4aa3ff)">{HANDLE}</b></span></a>')
    return a(YT_URL, YT_SVG, "YouTube") + a(X_URL, X_SVG, "X")

import sitenav_ui as UI   # top bar + sidebar markup (t320/t321/t323)

# Dashboard-only controls, shown in the top bar's settings popover (ids used by dashboard.html's script).
DASH_CTL = ('<span id="status">loading…</span><button class="pri" id="refresh">⟳ Manual refresh</button>'
            '<label title="How often this page pulls the latest data on this device. Saved in this browser.">Refresh my view every <select id="interval" aria-label="Refresh my view every"></select></label><span id="msg"></span>')

def header_html(active=""):
    """The shared top bar (logo, The Wire / Sources / Newsletter, Follow us on YouTube / X, search, theme, menu) + the sidebar menu."""
    return UI.topbar(sys.modules[__name__], active) + UI.drawer(sys.modules[__name__], active)

def nav_html(active=""):
    """Kept for callers of the old tab strip: the tab strip is gone (t321); the sidebar menu is part of header_html()."""
    return ""

def intro_html(page):
    title = PAGES[page][1].split(" | ")[0]
    if page == "home": title = "The Wire"
    return UI.pagehead(title, PAGES[page][3])

def site_top(page):
    """Top bar + sidebar + page title and one-line description, for the top of a standalone page's <body>."""
    return header_html(PAGES[page][0]) + intro_html(page)

def dashboard_top():
    """Top bar + sidebar + title block for dashboard.html (server.py replaces <!--BN_TOP--> with this)."""
    m = sys.modules[__name__]
    return UI.topbar(m, "threat", DASH_CTL) + UI.drawer(m, "threat") + UI.pagehead("The Wire", PAGES["home"][3])

# Per-page share cards (BN Signal tile). New filenames bust YouTube/X/Facebook link-preview caches (pulse-logo cleanup, Nov 1).
OG_IMAGES = {"newsletter": "/icons/icon-og-newsletter-bn3.png"}

def head_html(page, path=None):
    """<title>, description, canonical, Open Graph and Twitter tags + the shared nav stylesheet, for a standalone page's <head>."""
    _, title, desc, _ = PAGES[page]
    url = SITE + (path if path is not None else "/" + page)
    E = lambda s: html.escape(s, quote=True)
    img = SITE + OG_IMAGES.get(page, "/icons/icon-og-1200x630.png")
    return (UI.THEME_SCRIPT + f'<title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="{E(url)}">'
            f'<meta property="og:type" content="website"><meta property="og:site_name" content="{BRAND}"><meta property="og:title" content="{E(title)}">'
            f'<meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{E(url)}"><meta property="og:image" content="{img}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{img}"><meta name="twitter:site" content="{HANDLE}"><meta name="twitter:title" content="{E(title)}">'
            f'<meta name="twitter:description" content="{E(desc)}"><link rel="stylesheet" href="/sitenav.css"><script src="/sitenav.js" defer></script>')

def data():
    t = []
    for g, it in tabs():
        t.append({"key": it[0], "hash": it[1], "label": it[2], "group": g, "title": it[3], "desc": it[4], "hidden": bool(len(it) > 5 and it[5])})
    return {"groups": [g for g, _ in NAV], "tabs": t, "brand": BRAND, "tagline": TAGLINE, "site": SITE,
            "home": {"title": PAGES["home"][1], "desc": PAGES["home"][2]}, "social": social_html(),
            "plain": {it[0]: UI.plain(it[2]) for g, it in tabs()}}

FONTS = ("montserrat-latin-wght-normal.woff2", "inter-latin-wght-normal.woff2")

def handle_get(path, qs):
    if path == "/sitenav.css":
        with open(os.path.join(BASE, "static", "sitenav.css"), "rb") as fh: return 200, fh.read(), "text/css"
    if path.startswith("/fonts/"):
        name = path[7:]
        if name in FONTS:
            with open(os.path.join(BASE, "static", "fonts", name), "rb") as fh: return 200, fh.read(), "font/woff2"
        return 404, {"error": "not found"}
    if path == "/sitenav.js":
        with open(os.path.join(BASE, "static", "sitenav.js"), "r", encoding="utf-8") as fh: js = fh.read()
        js = js.replace("/*BN_SITENAV_DATA*/null", json.dumps(data(), ensure_ascii=False))
        return 200, js.encode("utf-8"), "application/javascript"
    return 404, {"error": "not found"}
