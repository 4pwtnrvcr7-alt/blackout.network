"""Deactivated pages (Matt, voice, Nov 24 2026 12:23 AM ET; mesh chat and the "unlisted" state added 7:50 AM ET): pages pulled from the site.

ONE list drives everything: menus (sitenav/sitenav_ui/menu5, the "/" intro menu, the Wire menu), footers, the sitemap/llms.txt,
the client-side link guard (/linkguard.js) and a temporary 302 to "/" for every deactivated route and its subpaths (server.py).
Nothing is deleted: templates, handlers, JS/CSS, data and the APIs behind these pages stay in the repo and keep running.

Reactivate one page: delete its row below (or set Render env BN_DEACTIVATE_PAGES=0 to bring all of them back) and redeploy.

Per-page state (Matt, Nov 24 2026 7:51 AM ET), the 4th column:
  "off"       the route 302s to "/" and every link to it is removed.
  "unlisted"  the route still serves (200) because newsletter emails link to it, but it is removed from every menu,
              footer, the homepage, the sitemap/llms.txt and every internal link, the same as "off".
"""
import os, json
from urllib.parse import urlsplit

# (name Matt used, nav keys in sitenav.NAV / sitenav_ui.MENU3, route prefixes (each also covers its subpaths), state "off" | "unlisted")
DEACTIVATED_PAGES = [
    ("Live",                 {"live"},            ["/live", "/dashboard"], "off"),
    ("Background Noise",     {"noise"},           ["/noise"], "off"),
    ("Solar & Seismic",      {"solar_seismic"},   ["/solar", "/solar_seismic", "/solar-seismic"], "off"),
    ("AI Threats",           {"ai"},              ["/ai", "/aithreats", "/ai-threats"], "off"),
    ("Crime",                {"@crime"},          ["/crime"], "unlisted"),
    ("Starlink",             {"starlink"},        ["/network/starlink"], "off"),
    ("Midterms 2026",        {"midterms"},        ["/midterms", "/election", "/elections"], "off"),
    ("Politics",             {"politics"},        ["/politics"], "off"),
    ("Government",           {"gov"},             ["/government"], "off"),
    ("Gun Laws",             {"gunlaws"},         ["/gunlaws"], "off"),
    ("Key Figures",          {"figures"},         ["/figures", "/elon"], "off"),
    ("Preppers",             {"preppers"},        ["/preppers"], "off"),
    ("Local Resources",      {"res"},             ["/resources"], "off"),
    ("Offline Maps",         {"maps"},            ["/maps"], "off"),
    ("First Aid",            {"med"},             ["/medical", "/first-aid"], "off"),
    ("Bushcraft",            {"bush"},            ["/bushcraft"], "off"),
    ("Sources",              {"sources"},         ["/sources"], "unlisted"),
    ("How We Score",         {"@scoring"},        ["/scoring", "/about/scoring"], "unlisted"),
    ("SpaceX",               {"spacex"},          ["/spacex"], "off"),   # newsletter_v2 links /spacex, but /spacex is only a tab of /live (no page of its own), so it cannot stay up while /live is off
    ("CERN & LHC",           {"@cern"},           ["/cern", "/lhc"], "off"),
    ("Private Jets",         {"jets"},            ["/jets"], "off"),   # Matt said "private chats" on voice; the menu item is Private Jets
    ("Games",                {"games"},           ["/games"], "off"),
    ("Mesh Chat",            {"mesh-chat"},       ["/mesh/chat"], "off"),   # Nov 24 7:50 AM ET (Matt): "private chats" also means the off-grid mesh chat; /mesh and /mesh/guide stay up
]

ON = os.environ.get("BN_DEACTIVATE_PAGES", "1") != "0"
KEYS = frozenset(k for _, ks, _, _st in DEACTIVATED_PAGES for k in ks) if ON else frozenset()
PREFIXES = tuple(p for _, _, ps, _st in DEACTIVATED_PAGES for p in ps) if ON else ()          # hidden: links, menus, sitemap
REDIRECT_PREFIXES = tuple(p for _, _, ps, st in DEACTIVATED_PAGES if st == "off" for p in ps) if ON else ()   # 302 to "/"
# dashboard #hash tabs that belonged to the deactivated pages (old "/#noise" and "/live#noise" links)
HASHES = frozenset({"noise", "solar", "solar_seismic", "ai", "midterms", "politics", "government", "gunlaws", "figures", "elon", "preppers",
                    "resources", "maps", "medical", "bushcraft", "sources", "spacex", "jets", "games"}) if ON else frozenset()
_HOSTS = ("", "blackout.network", "www.blackout.network")

def key_off(key):
    return key in KEYS

def _norm(path):
    return (path or "").split("?", 1)[0].split("#", 1)[0].lower().rstrip("/") or "/"

def is_off(path):
    """True if a path is a hidden page ("off" or "unlisted") or one of its subpaths (case-insensitive, trailing slash ok):
    no menu entry, footer, sitemap row or internal link points at it."""
    if not ON: return False
    p = _norm(path)
    return any(p == x or p.startswith(x + "/") for x in PREFIXES)

def redirects(path):
    """True if a request path must 302 to "/" (state "off" only; "unlisted" pages keep serving for newsletter links)."""
    if not ON: return False
    p = _norm(path)
    return any(p == x or p.startswith(x + "/") for x in REDIRECT_PREFIXES)

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
                                                     "groups": [list(ps) for _, _, ps, st in DEACTIVATED_PAGES if st == "unlisted"] if ON else [],
                                                     "live": is_off("/live")}, separators=(",", ":")) + "</script>")

def _group(path):
    """Prefixes of the "unlisted" page a path belongs to (an unlisted page keeps its own internal links, e.g. /crime?place=...)."""
    if not ON or not path: return ()
    p = _norm(path)
    for _, _, ps, st in DEACTIVATED_PAGES:
        if st == "unlisted" and any(p == x or p.startswith(x + "/") for x in ps): return tuple(ps)
    return ()



def report():
    return [{"name": n, "keys": sorted(k), "routes": p, "state": st} for n, k, p, st in DEACTIVATED_PAGES]

import re as _re
_CANON = _re.compile(r'<link\b[^>]*\brel=["\']canonical["\'][^>]*\bhref=["\']https?://(?:www\.)?blackout\.network(/[^"\'#?]*)', _re.I)
_A = _re.compile(r'(\s*(?:·|&middot;|&#183;|\|)\s*)?<a\b[^>]*?\bhref=(["\'])([^"\']*)\2[^>]*>(?:(?!</a>).)*?</a>(\s*(?:·|&middot;|&#183;|\|)\s*)?', _re.S)
def clean(fragment, here=None):
    """Remove links to deactivated pages from a server-side HTML fragment (footers, related-links rows), with one
    adjacent " · " separator so the row still reads cleanly. Other links and text are left as they are.
    here = the page being served (default: its canonical URL); an "unlisted" page keeps links to itself (e.g. /crime?place=...)."""
    if not ON or not fragment: return fragment
    if here is None:
        mc = _CANON.search(fragment[:20000]); here = mc.group(1) if mc else ""
    own = _group(here)
    def rep(m):
        if not href_off(m.group(3)): return m.group(0)
        if own:
            try: hp = _norm(urlsplit(m.group(3)).path)
            except Exception: hp = ""
            if hp and any(hp == x or hp.startswith(x + "/") for x in own): return m.group(0)
        pre, post = m.group(1) or "", m.group(4) or ""
        return pre if (pre and post) else ""
    return _A.sub(rep, fragment)
