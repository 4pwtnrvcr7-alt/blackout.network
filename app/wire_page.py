"""The Wire listing page (Nov 14 2026 rethink): GET /wire.

A static HTML shell plus /api/wire_page/app.js|app.css. The digest, 24-hour bulletin,
Confirmed/Single-source toggle and accordion drawers are built in the browser from the
existing public APIs (/api/state, /api/state_items, /api/social). This module never
reads blackout.db, never starts a thread, and never builds the feed on the server.

Bare /wire and /wire/ are dispatched from story.handle_get so every /wire/<16-hex>
story URL stays on story.py unchanged. Featured-notice JSON is the same desk_stories
feature_card already used on the homepage, inlined into the shell (one small file read).

Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py or config.json."""
import json, os, re, time
import sitenav

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "wire_page_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css"}

# One-slot caches, keyed by file mtime. Never grow.
_SHELL = {"key": None, "html": None}
_FILE = {}

def _mt(*paths):
    out = []
    for p in paths:
        try: out.append(os.path.getmtime(p))
        except OSError: out.append(0)
    return tuple(out)

def _file(name):
    if name not in FILES: return None
    path = os.path.join(STATIC, name)
    try: mt = os.path.getmtime(path)
    except OSError: return None
    hit = _FILE.get(name)
    if hit and hit[0] == mt: return hit[1]
    with open(path, "rb") as f: data = f.read()
    _FILE.clear()
    _FILE[name] = (mt, data)
    return data

def _notice():
    try:
        import desk_stories as DS
        return DS.feature_card()
    except Exception:
        return None

def _shell():
    key = _mt(
        os.path.join(BASE, "wire_page.py"),
        os.path.join(STATIC, "app.js"),
        os.path.join(STATIC, "app.css"),
        os.path.join(BASE, "sitenav.py"),
        os.path.join(BASE, "sitenav_ui.py"),
    )
    if _SHELL["key"] == key and _SHELL["html"]:
        return _SHELL["html"]
    head = sitenav.head_html("wire", path="/wire")
    html = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        + head +
        "<link rel=\"stylesheet\" href=\"/theme.css\">"
        "<link rel=\"icon\" href=\"/favicon.ico?v=5\" sizes=\"any\">"
        "<link rel=\"stylesheet\" href=\"/api/wire_page/app.css\">"
        "<link rel=\"preload\" href=\"/api/state\" as=\"fetch\" crossorigin>"
        "</head><body>"
        "<a class=\"skip\" href=\"#main\">Skip to content</a>"
        + sitenav.header_html("threat") +
        "<main class=\"wrap bn-wire bnt-pg bnt-lt w-loading\" id=\"main\" aria-busy=\"true\">"
        "<p class=\"kicker\">The Wire</p>"
        "<h1>What matters now</h1>"
        "<p class=\"dek\">Every ranked alert, newest changes first.</p>"
        "<div class=\"w-how bnt-peek\" tabindex=\"0\" aria-expanded=\"false\"><span class=\"w-how-t\">How to read The Wire</span>"
        "<div class=\"bnt-peek-d\"><div><p>A 24-hour change bulletin, then a ranked digest of live threats and emergencies. "
        "Open any row for what we know, what to do, sources, and any related @BlkoutNtw video. "
        "Ranks are the live 0–10 scores.</p>"
        "<div class=\"bnt-key\"><span class=\"c\">Calm <b>0–3</b></span><span class=\"e\">Elevated <b>4–6</b></span><span class=\"h\">High <b>7–10</b></span></div>"
        "</div></div></div>"
        "<div class=\"w-uprow\"><span id=\"w-up\"></span><p class=\"updated\" id=\"w-updated\">Loading the live feed…</p></div>"
        "<section class=\"bulletin\" id=\"w-bulletin\">"
        "<h2>Last 24 hours</h2>"
        "<ul id=\"w-bullets\"><li class=\"sk\"></li><li class=\"sk\"></li></ul>"
        "<div class=\"coming\" id=\"w-coming\" hidden></div>"
        "</section>"
        "<div class=\"leadrow\">"
        "<div class=\"stats\" id=\"w-stats\"><div class=\"stat high\"><b>&ndash;</b><span>High · 7–10</span></div><div class=\"stat elev\"><b>&ndash;</b><span>Elevated · 4–6</span></div><div class=\"stat low\"><b>&ndash;</b><span>Lower · 0–3</span></div></div>"
        "<div class=\"seg\" role=\"group\" aria-label=\"Source filter\">"
        "<button type=\"button\" data-mode=\"confirmed\" aria-pressed=\"true\">Confirmed</button>"
        "<button type=\"button\" data-mode=\"single\" aria-pressed=\"false\">Single-source</button>"
        "</div></div>"
        "<div id=\"w-feed\"><div class=\"w-sk\" aria-hidden=\"true\"><div class=\"bandh\"><h2 class=\"high\">High</h2></div>" + "<div class=\"sk-row\"></div>" * 8 + "</div></div>"
        "<p class=\"err\" id=\"w-err\" hidden></p>"
        "</main>"
        "<footer class=\"ft\">Research only: BLACKOUT.NETWORK is not an official warning service. "
        "Always follow official instructions from local authorities. · "
        "<a href=\"/scoring\">How we score</a> · <a href=\"/newsletter\">Newsletter</a> · "
        "<a href=\"/sources\">Sources</a> · <a href=\"/privacy\">Privacy</a> · "
        "<a href=\"/tos\">Terms</a><br>"
        "BLACKOUT.NETWORK · PO Box 1228, Lake Mary, FL 32746</footer>"
        "<script>window.BN_WIRE_NOTICE=null;</script>"
        "<script src=\"/api/wire_page/app.js\" defer></script>"
        "</body></html>"
    )
    _SHELL["key"] = key
    _SHELL["html"] = html
    return html

def page(noindex=False):
    """HTML shell with the current featured notice swapped in. The shell itself is cached in one slot."""
    html = _shell().replace(
        "window.BN_WIRE_NOTICE=null;",
        "window.BN_WIRE_NOTICE=" + json.dumps(_notice(), ensure_ascii=False) + ";",
        1,
    )
    if noindex and 'name="robots"' not in html:
        html = html.replace("</head>", '<meta name="robots" content="noindex,nofollow,noarchive"></head>', 1)
    return 200, html.encode("utf-8"), "text/html"

def handle_get(path, qs):
    if path in ("/wire", "/wire/"):
        return page()
    if path.startswith("/api/wire_page/"):
        name = path[len("/api/wire_page/"):]
        if not re.fullmatch(r"app\.(js|css)", name):
            return 404, {"error": "not found"}
        data = _file(name)
        if data is None:
            return 404, {"error": "not found"}
        return 200, data, FILES[name]
    # /wire/<id> stays on story.py; this module must not claim it.
    return 404, {"error": "not found"}
