"""Deactivated pages (Matt, voice, Nov 24 2026 12:23 AM ET; mesh chat and the "unlisted" state added 7:50 AM ET): pages pulled from the site.

ONE list drives everything: menus (sitenav/sitenav_ui/menu5, the "/" intro menu, the Wire menu), footers, the sitemap/llms.txt,
the client-side link guard (/linkguard.js) and a temporary 302 to "/" for every deactivated route and its subpaths (server.py).
Nothing is deleted: templates, handlers, JS/CSS, data and the APIs behind these pages stay in the repo and keep running.

Reactivate one page: delete its row below (or set Render env BN_DEACTIVATE_PAGES=0 to bring all of them back) and redeploy.

Per-page state (Matt, Nov 24 2026 7:51 AM ET), the 4th column. Reworked pages (solo.py, Nov 24 2026 pt1846u) move from "off" to
"unlisted" so they serve for review but stay off every menu until Matt approves them:
  "off"       the route 302s to "/" and every link to it is removed.
  "unlisted"  the route still serves (200) because newsletter emails link to it, but it is removed from every menu,
              footer, the homepage, the sitemap/llms.txt and every internal link, the same as "off".
"""
import os, json
from urllib.parse import urlsplit

# (name Matt used, nav keys in sitenav.NAV / sitenav_ui.MENU3, route prefixes (each also covers its subpaths), state "off" | "unlisted")
DEACTIVATED_PAGES = [
    ("Live",                 {"live"},            ["/live", "/dashboard"], "off"),
    ("Background Noise",     {"noise"},           ["/noise"], "unlisted"),
    ("Solar & Seismic",      {"solar_seismic"},   ["/solar", "/solar_seismic", "/solar-seismic"], "off"),
    ("AI Threats",           {"ai"},              ["/ai", "/aithreats", "/ai-threats"], "unlisted"),
    ("Crime",                {"@crime"},          ["/crime"], "unlisted"),
    ("Starlink",             {"starlink"},        ["/network/starlink", "/grid/starlink"], "off"),
    ("Midterms 2026",        {"midterms"},        ["/midterms", "/election", "/elections"], "off"),
    ("Politics",             {"politics"},        ["/politics"], "unlisted"),
    ("Government",           {"gov"},             ["/government"], "unlisted"),
    ("Gun Laws",             {"gunlaws"},         ["/gunlaws"], "unlisted"),
    ("Key Figures",          {"figures"},         ["/figures", "/elon"], "unlisted"),
    ("Preppers",             {"preppers"},        ["/preppers"], "unlisted"),
    ("Local Resources",      {"res"},             ["/resources"], "off"),
    ("Offline Maps",         {"maps"},            ["/maps"], "off"),
    ("First Aid",            {"med"},             ["/medical", "/first-aid"], "unlisted"),
    ("Bushcraft",            {"bush"},            ["/bushcraft"], "unlisted"),
    ("Sources",              {"sources"},         ["/sources"], "unlisted"),
    ("How We Score",         {"@scoring"},        ["/scoring", "/about/scoring"], "unlisted"),
    ("SpaceX",               {"spacex"},          ["/spacex"], "unlisted"),   # newsletter_v2 links /spacex, but /spacex is only a tab of /live (no page of its own), so it cannot stay up while /live is off
    ("CERN & LHC",           {"@cern"},           ["/cern", "/lhc"], "off"),
    ("Private Jets",         {"jets"},            ["/jets"], "off"),   # Matt said "private chats" on voice; the menu item is Private Jets
    ("Games",                {"games"},           ["/games"], "unlisted"),
    ("Mesh Chat",            {"mesh-chat"},       ["/mesh/chat"], "off"),   # Nov 24 7:50 AM ET (Matt): "private chats" also means the off-grid mesh chat; /mesh and /mesh/guide stay up
    ("The Grid (old menu item)", {"grid"},        [], "off"),   # Nov 24 2026 (Matt): the old "Energy Grid"/"The Grid" menu key stays hidden; The Grid is the "net" item at /grid (no route is redirected by this row)
]

# "off" pages whose content moved to another page: the 302 goes there instead of "/".
MOVED = {}
# Nov 24 2026 8:32 AM ET (Matt): The Grid's canonical URL is /grid. /network and every /network/<path> 302 to the same path under /grid
# (path and query kept, so /network/status/aws -> /grid/status/aws; #status survives because browsers keep the fragment).
# The old full-screen /grid page (gridpage.py) is replaced by the merged page; its code and /api/gridpage/* stay.
RENAMED = {"/network": "/grid"}

def renamed(path, query=""):
    """Location for a renamed route (RENAMED, subpaths included, case-insensitive prefix), or None."""
    pth = (path or "").split("?", 1)[0]
    low = pth.lower()
    for old, new in RENAMED.items():
        if low == old or low == old + "/" or low.startswith(old + "/"):
            rest = pth[len(old):].rstrip("/") if low != old + "/" else ""
            return new + rest + ("?" + query if query else "")
    if low in ("/grid", "/grid/") and pth != "/grid":   # /GRID, /Grid/, /grid/ -> /grid
        return "/grid" + ("?" + query if query else "")
    return None

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

def location(path):
    """Where an "off" page's 302 goes: its new home if it was merged into another page (MOVED), else "/"."""
    p = _norm(path)
    for x, to in MOVED.items():
        if p == x or p.startswith(x + "/"): return to
    return "/"

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
