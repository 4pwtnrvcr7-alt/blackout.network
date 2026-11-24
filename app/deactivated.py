"""Deactivated pages (Matt, voice, Nov 24 2026 12:23 AM ET): 21 pages pulled from the site.

ONE list drives everything: menus (sitenav/sitenav_ui/menu5, the "/" intro menu, the Wire menu), footers, the sitemap/llms.txt,
the client-side link guard (/linkguard.js) and a temporary 302 to "/" for every deactivated route and its subpaths (server.py).
Nothing is deleted: templates, handlers, JS/CSS, data and the APIs behind these pages stay in the repo and keep running.

Reactivate one page: delete its row below (or set Render env BN_DEACTIVATE_PAGES=0 to bring all of them back) and redeploy."""
import os, json
from urllib.parse import urlsplit

# (name Matt used, nav keys in sitenav.NAV / sitenav_ui.MENU3, route prefixes; each prefix also covers its subpaths)
DEACTIVATED_PAGES = [
    ("Live",                 {"live"},            ["/live", "/dashboard"]),
    ("Background Noise",     {"noise"},           ["/noise"]),
    ("Solar & Seismic",      {"solar_seismic"},   ["/solar", "/solar_seismic", "/solar-seismic"]),
    ("AI Threats",           {"ai"},              ["/ai", "/aithreats", "/ai-threats"]),
    ("Crime",                {"@crime"},          ["/crime"]),
    ("Starlink",             {"starlink"},        ["/network/starlink"]),
    ("Midterms 2026",        {"midterms"},        ["/midterms", "/election", "/elections"]),
    ("Politics",             {"politics"},        ["/politics"]),
    ("Government",           {"gov"},             ["/government"]),
    ("Gun Laws",             {"gunlaws"},         ["/gunlaws"]),
    ("Key Figures",          {"figures"},         ["/figures", "/elon"]),
    ("Preppers",             {"preppers"},        ["/preppers"]),
    ("Local Resources",      {"res"},             ["/resources"]),
    ("Offline Maps",         {"maps"},            ["/maps"]),
    ("First Aid",            {"med"},             ["/medical", "/first-aid"]),
    ("Bushcraft",            {"bush"},            ["/bushcraft"]),
    ("Sources",              {"sources"},         ["/sources"]),
    ("How We Score",         {"@scoring"},        ["/scoring", "/about/scoring"]),
    ("SpaceX",               {"spacex"},          ["/spacex"]),
    ("CERN & LHC",           {"@cern"},           ["/cern", "/lhc"]),
    ("Private Jets",         {"jets"},            ["/jets"]),   # Matt said "private chats" on voice; the menu item is Private Jets
    ("Games",                {"games"},           ["/games"]),
]

ON = os.environ.get("BN_DEACTIVATE_PAGES", "1") != "0"
KEYS = frozenset(k for _, ks, _ in DEACTIVATED_PAGES for k in ks) if ON else frozenset()
PREFIXES = tuple(p for _, _, ps in DEACTIVATED_PAGES for p in ps) if ON else ()
# dashboard #hash tabs that belonged to the deactivated pages (old "/#noise" and "/live#noise" links)
HASHES = frozenset({"noise", "solar", "solar_seismic", "ai", "midterms", "politics", "government", "gunlaws", "figures", "elon", "preppers",
                    "resources", "maps", "medical", "bushcraft", "sources", "spacex", "jets", "games"}) if ON else frozenset()
_HOSTS = ("", "blackout.network", "www.blackout.network")

def key_off(key):
    return key in KEYS

def is_off(path):
    """True if a request path is a deactivated page or one of its subpaths (case-insensitive, trailing slash ok)."""
    if not ON: return False
    p = (path or "").split("?", 1)[0].split("#", 1)[0].lower().rstrip("/") or "/"
    return any(p == x or p.startswith(x + "/") for x in PREFIXES)

def href_off(href):
    """True if an <a href> on our own site points at a deactivated page (incl. "/#noise" / "/live#noise" tab links)."""
    if not ON or not href: return False
    try: u = urlsplit(href)
    except Exception: return False
    if (u.netloc or "").lower() not in _HOSTS: return False
    if u.scheme not in ("", "http", "https"): return False
    if not u.path and not u.netloc: return False          # "#s6", "?x" on the same page
    if is_off(u.path or "/"): return True
    return (u.path in ("", "/", "/index.html")) and (u.fragment or "").lower() in HASHES

def js_config():
    """Inline <script> (every full HTML page, server.pwa_head): window.BN_OFF for the link guard, menus and the hash bridges."""
    return ("<script>window.BN_OFF=" + json.dumps({"on": ON, "prefixes": list(PREFIXES), "hashes": sorted(HASHES),
                                                     "live": is_off("/live")}, separators=(",", ":")) + "</script>")

def report():
    return [{"name": n, "keys": sorted(k), "routes": p} for n, k, p in DEACTIVATED_PAGES]

import re as _re
_A = _re.compile(r'(\s*(?:·|&middot;|&#183;|\|)\s*)?<a\b[^>]*?\bhref=(["\'])([^"\']*)\2[^>]*>(?:(?!</a>).)*?</a>(\s*(?:·|&middot;|&#183;|\|)\s*)?', _re.S)
def clean(fragment):
    """Remove links to deactivated pages from a server-side HTML fragment (footers, related-links rows), with one
    adjacent " · " separator so the row still reads cleanly. Other links and text are left as they are."""
    if not ON or not fragment: return fragment
    def rep(m):
        if not href_off(m.group(3)): return m.group(0)
        pre, post = m.group(1) or "", m.group(4) or ""
        return pre if (pre and post) else ""
    return _A.sub(rep, fragment)
